# gateway.py ESPNOW-MQTT gateway
# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers
# Assumes an ESP32 including S2 or S3 variants. At time of writing  standard
# ESP32 seems most reliable.

# Aim is to facilitate micropower nodes which spend most of the time in deepsleep.
# They wake periodically to read sensors and transmit the data to the gateway. Any
# subscribed messages are relayed to the node immediately afterwards, enabling the
# node to go back to sleep.

# Subscriptions are normally directed to a single node. This is identified by a bytes
# object ubinascii.hexlify(machine.unique_id()) which (on ESP32) corresponds to the
# MAC address.

import json
from mqtt_as import MQTTClient
from mqtt_local import config
import uasyncio as asyncio
from ubinascii import hexlify, unhexlify
from primitives import RingbufQueue


class Gateway:
    def __init__(self, debug, qlen, lpmode):
        MQTTClient.DEBUG = debug  # Optional debug statements.
        self.debug = debug
        self.qlen = qlen
        self.lpmode = lpmode
        self.allnodes, qos = config["gwtopic"]  # Default topic sends to all nodes
        self.queues = {}  # Key node ID, value RingbufQueue of pending messages
        # Dict of current subscriptions. All nodes are subscribed to default topic.
        # Key topic, value [qos, {node_id...}] Set of nodes subscribed to that topic.
        self.topics = {self.allnodes: [qos, set()]}
        self.connected = False
        self.client = MQTTClient(config)

    async def run(self):
        try:
            await self.client.connect()
        except OSError:
            print("Connection failed.")
            return
        asyncio.create_task(self.up())
        asyncio.create_task(self.down())
        asyncio.create_task(self.messages())
        await self.do_esp()  # Forever

    async def down(self):
        client = self.client
        while True:
            await client.down.wait()  # Pause until connectivity changes
            client.down.clear()
            self.connected = False
            self.debug and print("WiFi or broker is down.")

    async def up(self):
        client = self.client
        while True:
            await client.up.wait()
            client.up.clear()
            self.connected = True
            self.debug and print("We are connected to broker.")
            for topic in self.topics:
                await client.subscribe(topic, self.topics[topic][0])

    # Send an ESPNOW message. Return True on success. Failure can occur because
    # node is OOR, powered down or failed. Other failure causes are
    # node not initialised or WiFi not active due to outage recovery in progress.
    async def do_send(self, mac, msg):
        espnow = self.client._espnow
        try:
            return await espnow.asend(mac, msg)
        except OSError:
            return False

    # If no messages are queued try to send an ESPNow message. If this fails,
    # queue for sending when node is awake/in range.
    # If messages are queued or GW is in low power mode, queue the current message.
    async def try_send(self, node_id, ms):
        assert node_id in self.queues, f"Unknown node_id {node_id}"
        queue = self.queues[node_id]
        # Messages are queued: node is asleep/AWOL. Or nodes are in low power mode.
        if queue.qsize() or self.lpmode:
            try:
                queue.put_nowait(ms)
            except IndexError:
                pass  # Overwrite oldest when full
        else:  # No queued messages. May be awake.
            mac = unhexlify(node_id)
            if not await self.do_send(mac, ms):  # If send fails queue the message
                queue.put_nowait(ms)  # Empty so can't overflow

    # On an incoming ESPNOW message, publish it. Then relay any stored subscribed messages
    # back. Incoming messages are a JSON encoded 4-list:
    # [topic:str, message:str, retain:bool, qos:int]
    # outages: Incoming ESPNow messages are discarded. The response is an outage message
    # plus any subs that were queued before the outage. Node periodically polls by sending
    # a message.
    async def do_esp(self):
        ack = json.dumps(["ACK", "ACK"])
        outage = json.dumps(["OUT", "OUT"])
        client = self.client
        espnow = client._espnow
        async for mac, msg in espnow:
            try:
                message = json.loads(msg)
            except ValueError:  # Node is probably pinging
                continue  # no response required
            node = hexlify(mac)  # MAC as hex bytes
            #print(f"ESPnow {mac} node {node} message: {message} msg: {msg}")
            if node not in self.queues:  # First contact. Initialise.
                self.queues[node] = RingbufQueue([None] * self.qlen)  # Create a message queue
                espnow.add_peer(mac)
                self.topics[self.allnodes][1].add(node)  # Add to default "all nodes" topic
            if len(message) == 2:  # It's a subscription.
                topic, qos = message
                if topic in self.topics:  # topic is already a client subscription
                    self.topics[topic][1].add(node)  # add node to set of subscribed nodes
                    if self.debug and qos != self.topics[topic][0]:
                        print("Warning: attempt to change qos of existing subscription:", topic)
                else:  # New subscription
                    self.topics[topic] = [qos, {node}]
                    await client.subscribe(topic, qos)
                continue
            if len(message) != 4:  # Malformed
                self.debug and print(f"Malformed message {message} from node {node}")
                continue
            # args topic, message, retain, qos
            #print(f"Node {node} topic {message[0]} message {message[1]} retain {message[2]} qos {message[3]}")
            if message[3] & 4:  # Bit 2 (qos==5) indicates ACK
                await self.do_send(mac, ack)  # Don't care if this fails, app will retry
                message[3] &= 3
            # Try to ensure .connected is current. Aim is to avoid many pending .publish tasks.
            asyncio.sleep_ms(0)
            if self.connected:  # Run asynchronously to ensure fast response to ESPNow
                #print("Publish")
                asyncio.create_task(client.publish(*message))
            else:  # Discard message, send outage response
                await self.do_send(mac, outage)
            queue = self.queues[node]  # Queue for current node
            while queue.qsize():  # Handle all queued messages for that node
                ms = queue.peek()  # Retrieve oldest message without removal
                self.debug and print(f"Sending to {node} message {ms}")
                # Relay any subs back to mac. Note asend can be pessimistic so can get dupes
                if await self.do_send(mac, ms):  # Message was successfully sent
                    queue.get_nowait()  # so remove from queue
                else:
                    self.debug and print(f"Peer {hexlify(mac)} not responding")
                    break  # Leave on queue. Don't send more. Try again on next incoming.

    # Manage message queues for each node.
    # Both ESPNow and mqtt_as use bytes objects. json.dumps() returns strings.
    async def messages(self):
        async for topic, message, retained in self.client.queue:
            topic = topic.decode()  # Convert to strings
            message = message.decode()
            # queues key is node MAC as a ubinascii-format bytes object
            ms = json.dumps([topic, message, retained])
            try:
                for node_id in self.topics[topic][1]:  # For each node subscribed to topic
                    self.debug and print(f"Sending or queueing message {ms} to node {node_id}")
                    await self.try_send(node_id, ms)  # Send or queue on failure.
            except KeyError:
                self.debug and print(f"No nodes subscribed to topic {topic}")

    def close(self):
        self.client.close()


# Define configuration
config["keepalive"] = 120
config["queue_len"] = 1  # Use event interface with default queue


def run(debug=True, qlen=10, lpmode=True):
    gw = Gateway(debug, qlen, lpmode)
    try:
        asyncio.run(gw.run())
    finally:
        gw.close()
        _ = asyncio.new_event_loop()
