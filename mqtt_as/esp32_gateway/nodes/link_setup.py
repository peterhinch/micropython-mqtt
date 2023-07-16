# link_setup.py
# Adapt these lines
gateway = bytes.fromhex(b'2462abe6b0b5')  # ESP reference clone AP I/F
debug = True
# Case where WiFi AP channel is known
channel = 3  # WiFi AP channel
credentials = None  # Fixed channel

# If channel is unknown need
# channel = None
# credentials = ('ssid', 'password')
