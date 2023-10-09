from enum import Enum
import logging
import time

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
    
    #translate a command to appropriate dx, dy
def TranslateCommand(command : str, current_direction : int):
    if len(command) < 4:
        return 0, 0, current_direction
    if command.startswith("FW") or command.startswith("FS"):
        if current_direction == Direction.NORTH.value:
            return 0, int(command[2:]) // 10, current_direction
        elif current_direction == Direction.EAST.value:
            return int(command[2:]) // 10, 0, current_direction
        elif current_direction == Direction.SOUTH.value:
            return 0, -(int(command[2:]) // 10), current_direction
        elif current_direction == Direction.WEST.value:
            return -(int(command[2:]) // 10), 0, current_direction

    elif command.startswith("BW") or command.startswith("BS"):
        if current_direction == Direction.NORTH.value:
            return 0, -(int(command[2:]) // 10), current_direction
        elif current_direction == Direction.EAST.value:
            return -(int(command[2:]) // 10), 0, current_direction
        elif current_direction == Direction.SOUTH.value:
            return 0, (int(command[2:]) // 10), current_direction
        elif current_direction == Direction.WEST.value:
            return int(command[2:]) // 10, 0, current_direction

    elif command.startswith("BR"):
        if current_direction == Direction.NORTH.value:
            return 1, -3, Direction.WEST.value
        elif current_direction == Direction.EAST.value:
            return -3, -1, Direction.NORTH.value
        elif current_direction == Direction.SOUTH.value:
            return -1, 3, Direction.EAST.value
        elif current_direction == Direction.WEST.value:
            return 3, 1, Direction.SOUTH.value

    elif command.startswith("BL"):
        if current_direction == Direction.NORTH.value:
            return -1, -3, Direction.EAST.value
        elif current_direction == Direction.EAST.value:
            return -3, 1, Direction.SOUTH.value
        elif current_direction == Direction.SOUTH.value:
            return 1, 3, Direction.WEST.value
        elif current_direction == Direction.WEST.value:
            return 3, -1, Direction.NORTH.value

    elif command.startswith("FL"):
        if current_direction == Direction.NORTH.value:
            return -1, 3, Direction.WEST.value
        elif current_direction == Direction.EAST.value:
            return -3, -1, Direction.SOUTH.value
        elif current_direction == Direction.SOUTH.value:
            return 1, -3, Direction.EAST.value
        elif current_direction == Direction.WEST.value:
            return -3, -1, Direction.SOUTH.value

    elif command.startswith("FR"):
        if current_direction == Direction.NORTH.value:
            return 1, 3, Direction.EAST.value
        elif current_direction == Direction.EAST.value:
            return -3, 1, Direction.NORTH.value
        elif current_direction == Direction.SOUTH.value:
            return -1, -3, Direction.WEST.value
        elif current_direction == Direction.WEST.value:
            return -3, 1, Direction.NORTH.value
    else:
        logging.debug(f"[command]Unhandled command:{command}")
    return 0, 0, current_direction

def current_milli_time():
    return round(time.time() * 1000)