from Modules.AndroidModule import AndroidModule, AndroidMessage
import json
import logging
logging.basicConfig(level=logging.DEBUG)

btSvr = AndroidModule()
btSvr.connect()
btSvr.send(AndroidMessage("ROBOT_STATUS", "tesfrg"))
while True:
    msg_str = None
    try:
        msg_str = btSvr.receive()
        btSvr.send(AndroidMessage("ROBOT_STATUS", "tesfrg"))
    except OSError:
        print("Event set: Android connection dropped")

    if msg_str is None:
        continue
    message = json.loads(msg_str)
    print(message)