# Gateway startup
import time
time.sleep(4)  # Enable break-in at boot time
import gateway
gateway.run(debug=True, qlen=10, lpmode=True, use_ap_if=True)
