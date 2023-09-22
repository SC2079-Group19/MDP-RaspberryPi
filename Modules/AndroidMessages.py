import json
from enum import Enum

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
        super(InfoMessage, self).__init__(BluetoothHeader.ROBOT_STATUS.value, value)

class RobotLocMessage(AndroidMessage):
    def __init__(self, value : dict):
        super(RobotLocMessage, self).__init__(BluetoothHeader.ROBOT_LOCATION.value, str(value))

class ImageMessage(AndroidMessage):
    def __init__(self, value: str):
        super(ImageMessage, self).__init__(BluetoothHeader.IMAGE_INFO.value, value)

class ObstacleMessage(AndroidMessage):
    def __init__(self, v):
        pass
        #super().__init__(category, value)