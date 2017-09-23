# Distinguish responses from thosse of other unit
# mosquitto_sub -h 192.168.0.9 -t sonoff_1_result -q 1

from utime import sleep
sleep(4)
import sonoff

out = b'sonoff_1_result'
topics = {
    'led' : b'sonoff_led',  # Incoming subscriptions
    'relay' : b'sonoff_relay',
    'debug' : out,  # Outgoing publications
    'button' : out,
    'remote' : out,  # Set to None if no R/C decoder fitted
    'will' : out,
    }

sonoff.run(topics)
