<<<<<<< HEAD
from enum import Enum

class RobotStatus(Enum):
    READY = 1
    NAVIGATING = 2
    DETECTING_IMAGE = 3
    UNRESPONSIVE = 4
    CALCULATING_PATH = 5
    FINISH = 6

class Direction(int, Enum):
    NORTH = 0
    EAST = 2
    SOUTH = 4
    WEST = 6
    SKIP = 8

    def __int__(self):
        return self.value
    
class BluetoothHeader(str, Enum):
    ROBOT_CONTROL = 'ROBOT_CONTROL',
    ROBOT_STATUS = 'ROBOT_STATUS',
    ITEM_LOCATION = 'ITEM_LOCATION',
    ROBOT_LOCATION = 'ROBOT_LOCATION'

    def __int__(self):
=======
from enum import Enum

class RobotStatus(Enum):
    READY = 1
    NAVIGATING = 2
    DETECTING_IMAGE = 3
    UNRESPONSIVE = 4
    CALCULATING_PATH = 5
    FINISH = 6

class Direction(int, Enum):
    NORTH = 0
    EAST = 2
    SOUTH = 4
    WEST = 6
    SKIP = 8

    def __int__(self):
        return self.value
    
class BluetoothHeader(str, Enum):
    ROBOT_CONTROL = 'ROBOT_CONTROL',
    ROBOT_STATUS = 'ROBOT_STATUS',
    ITEM_LOCATION = 'ITEM_LOCATION',
    ROBOT_LOCATION = 'ROBOT_LOCATION'

    def __int__(self):
>>>>>>> 2812027a3028b02e581981e7d1b9c117707d9a6b
        return self.value