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