#import webrepl
#webrepl.start()
from utime import sleep
sleep(4)
import sonoff
sonoff.run(b'sonoff_result', b'sonoff_led', b'sonoff_relay')
