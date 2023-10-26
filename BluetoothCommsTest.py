from Modules.AndroidModule import AndroidModule
from Modules.AndroidMessages import AndroidMessage, InfoMessage, RobotLocMessage, \
    ImageMessage, BluetoothHeader, StatusMessage
from helper import RobotStatus, Direction, current_milli_time

import logging
logging.basicConfig(level=logging.DEBUG)

btSvr = AndroidModule()
btSvr.connect()
btSvr.send(InfoMessage("Commands queue finished."))
btSvr.send(StatusMessage(RobotStatus.FINISH))
# while True:
#     msg_str = None
#     try:
#         msg_str = btSvr.receive()
#         btSvr.send(AndroidMessage("ROBOT_STATUS", "tesfrg"))
#     except OSError:
#         print("Event set: Android connection dropped")

#     if msg_str is None:
#         continue
#     message = json.loads(msg_str)
#     print(message)