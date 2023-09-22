import json
from enum import Enum
from helper import RobotStatus

class BluetoothHeader(str, Enum):
    ROBOT_CONTROL = 'ROBOT_CONTROL',
    ROBOT_STATUS = 'ROBOT_STATUS',
    ITEM_LOCATION = 'ITEM_LOCATION',
    ROBOT_LOCATION = 'ROBOT_LOCATION',
    IMAGE_INFO = 'IMAGE_INFO'
    IMAGE_RESULT = 'IMAGE_RESULT'

    def __int__(self):
        return self.value

class AndroidMessage:
    def __init__(self, category:str, value:str):
        self._category = category
        self._value = value

    @property
    def category(self) -> str:
        return self._category

    @property
    def value(self) -> str:
        return self._value

    @property
    def json(self) -> str:
        return json.dumps({ "header": self._category, "data": self._value })
    
    @staticmethod
    def from_json(json_dct):
      msg = AndroidMessage(json_dct['header'],
                   json_dct['data'])
      return msg

class InfoMessage(AndroidMessage):
    def __init__(self, value: str):
        super().__init__(BluetoothHeader.ROBOT_STATUS.value, value)

class StatusMessage(AndroidMessage):
    def __init__(self, status: RobotStatus):
        if status == RobotStatus.READY:
            super().__init__(BluetoothHeader.ROBOT_STATUS.value, "Robot is ready")
        elif status == RobotStatus.NAVIGATING:
            super().__init__(BluetoothHeader.ROBOT_STATUS.value, "Robot navigating")
        elif status == RobotStatus.DETECTING_IMAGE:
            super().__init__(BluetoothHeader.ROBOT_STATUS.value, "RPI starting to capture image")
        elif status == RobotStatus.UNRESPONSIVE:
            super().__init__(BluetoothHeader.ROBOT_STATUS.value, "Robot is unresponsive")
        elif status == RobotStatus.CALCULATING_PATH:
            super().__init__(BluetoothHeader.ROBOT_STATUS.value, "Querying path finding server")
        elif status == RobotStatus.FINISH:
            super().__init__(BluetoothHeader.ROBOT_STATUS.value, "Robot finished path queue")

class RobotLocMessage(AndroidMessage):
    def __init__(self, value : dict):
        super().__init__(BluetoothHeader.ROBOT_LOCATION.value, str(value))

class ImageMessage(AndroidMessage):
    def __init__(self, value: str):
        super().__init__(BluetoothHeader.IMAGE_INFO.value, value)

class ObstacleMessage(AndroidMessage):
    def __init__(self, v : AndroidMessage):
        super().__init__(v.category, v.value)
        temp_obstacle = json.loads(self.value)
        self._obstacles = []
        if isinstance(temp_obstacle, dict):
            self._obstacles.append({
                "x": temp_obstacle['x'],
                "y": temp_obstacle['y'],
                "d": temp_obstacle['d'],
                "id": temp_obstacle['id'],
            })
        elif isinstance(temp_obstacle, list):
            for o in temp_obstacle:
                self._obstacles.append({
                    "x": o['x'],
                    "y": o['y'],
                    "d": o['d'],
                    "id": o['id'],
                })
    @property
    def obstacles(self) -> list:
        return self._obstacles