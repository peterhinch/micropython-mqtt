from mqtt_as import config, ESP32

# Include any cross-project settings.

if ESP32:
    config['ssid'] = 'my SSID'  # EDIT if you're using ESP32
    config['wifi_pw'] = 'my WiFi password'
