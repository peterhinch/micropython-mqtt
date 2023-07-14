# gwconfig.py Config file for ESPNow gateway

from collections import namedtuple, defaultdict

PubIn = namedtuple('PubIn', 'topic qos')  # Publication to gateway/nodes from outside
PubOut = namedtuple('PubOut', 'topic retain qos')  # Publication by gateway

gwcfg = defaultdict(lambda : None)
# Mandatory keys
gwcfg["debug"] = True  # Print debug info. Also causes more status messages to be published.
gwcfg["qlen"] = 10  # No. of messages to queue (for each node)
gwcfg["lpmode"] = True  # Set True if all nodes are micropower
gwcfg["use_ap_if"] = True  # Enable ESP8266 nodes by using AP interface
gwcfg["pub_all"] = PubIn("allnodes", 1)  # Publish to all nodes

# Optional keys
gwcfg["errors"] = PubOut("gw_errors", False, 1)  # Gateway publishes any errors.
gwcfg["status"] = PubOut("gw_status", False, 0)  # Status report
gwcfg["statreq"] = PubIn("gw_query", 0)  # Status request (not yet implemented)
gwcfg["ntp_host"] = "192.168.0.10"
gwcfg["ntp_offset"] = 1
