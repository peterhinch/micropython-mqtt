from sys import platform

# Include any cross-project settings.

config = {
    'client_id': hexlify(unique_id()),
    'server': None,
    'port': 0,
    'user': '',
    'password': '',
    'keepalive': 60,
    'ping_interval': 0,
    'ssl': False,
    'ssl_params': {},
    'response_time': 10,
    'clean_init': True,
    'clean': True,
    'max_repubs': 4,
    'will': None,
    'subs_cb': lambda *_: None,
    'wifi_coro': eliza,
    'connect_coro': eliza,
    'ssid': None,
    'wifi_pw': None,
}

if platform == 'esp32':
    config['ssid'] = 'my SSID'  # EDIT if you're using ESP32
    config['wifi_pw'] = 'my WiFi password'
