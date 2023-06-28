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
        self.queues = {}  # Key node ID, value RingbufQueue of pending messages
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
            for topic, qos in config["gwtopic"]:
                await client.subscribe(topic, qos)

    # Send an ESPNOW message. Return True on success. Failure can occur because
    # node is OOR, powered down or failed.
    # node not initialised, WiFi not active due to outage recovery
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
        if node_id not in self.queues:
            self.queues[node_id] = RingbufQueue([None] * self.qlen)  # Create a message queue
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
            #print(f"ESPnow {mac} message: {msg}")
            try:
                message = json.loads(msg)
            except ValueError:  # Node is probably pinging
                continue  # no response required
            node = hexlify(mac)  # MAC as hex bytes
            if node not in self.queues:  # First contact. May need to send it a message.
                self.queues[node] = RingbufQueue([None] * self.qlen)  # Create a message queue
                espnow.add_peer(mac)
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
    # Subscription message is json-encoded [node, payload] or ["all", payload].
    # Both ESPNow and mqtt_as use bytes objects. json.loads() returns strings.
    # Note re broadcast: Sent immediately for awake nodes but also queued. There is no feedback
    # on success so all nodes are queued, meaning that awake nodes get dupes,
    # Wildcard "ALL" messages don't have this issue so dupes are much rarer.
    async def messages(self):
        broadcast = b"FFFFFFFFFFFF"
        wildcard = (b"all", b"ALL")
        client = self.client
        espnow = client._espnow
        espnow.add_peer(unhexlify(broadcast))
        async for topic, msg, retained in client.queue:
            try:
                node, payload = json.loads(msg)
            except ValueError:  # Badly formatted message.
                continue
            node_id = node.encode()
            # queues key is node MAC as a ubinascii-format bytes object or b'all'
            ms = json.dumps([topic.decode(), payload, retained])
            print(f"Subs {node_id} ms {ms}")
            # Broadcast
            if node_id == broadcast:
                mac = unhexlify(node_id)
                await self.do_send(mac, ms)  # No return status. May be asleep.
                for q in self.queues.values():  # So put on every queue
                    q.put_nowait(ms)
            # Wildcard
            if node_id in wildcard:  # Sending to all known nodes
                for node_id in self.queues:  # Check every peer
                    await self.try_send(node_id, ms)  # Send, otherwise queue
                continue
            # Non-wildcard message. Validate the MAC address.
            try:
                mac = unhexlify(node_id)
            except ValueError:
                continue
            if len(mac) == 6:
                await self.try_send(node_id, ms)  # Send or queue on failure.

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
