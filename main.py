from datetime import datetime
import json
import logging
import os
from multiprocessing import Process, Manager, Queue, Lock, Event
import requests
import queue

from config import stm_command_prefixes, server_url, server_port
from helper import RobotStatus, Direction, BluetoothHeader
from Modules.AndroidModule import AndroidModule, AndroidMessage
from Modules.CameraModule import CameraModule
from Modules.StmModule import StmModule
from Modules.APIServer import APIServer


class RpiModule:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)

        self.camera = CameraModule()
        self.android = AndroidModule()
        self.stm = StmModule()
        self.server = APIServer()

        self._manager = Manager()

        self.path_queue = Queue()
        self.android_msgs = Queue()
        self.command_queue = Queue()

        self.movement_lock = Lock()

        self.start_movement = Event()

        self.obstacles = self._manager.list()
        self.robot_location = self._manager.dict()

        self.handle_android_msgs_process = None
        self.send_android_msgs_process = None
        self.handle_stm_msgs_process = None
        self.handle_commands_process = None

<<<<<<< HEAD
        self.robot_location["x"] = 1
        self.robot_location["y"] = 1
        self.robot_location["d"] = 0
=======
        self.robot_location = {
            "x": 1,
            "y": 1,
            "d": 0
        }
>>>>>>> 2812027a3028b02e581981e7d1b9c117707d9a6b

    def initialize(self, StartAndroid: bool = True, StartSTM: bool = True,
                   StartCamera: bool = True, CheckSvr: bool = True):
        if StartAndroid:
            self.android.connect()
        if StartSTM:
            self.stm.connect()
        if CheckSvr:
            self.check_server()
        if StartCamera:
            self.check_camera()

        if StartAndroid:
            self.handle_android_msgs_process = Process(target=self.handle_android_messages)
            self.send_android_msgs_process = Process(target=self.send_android_messages)
        if StartSTM:
            self.handle_stm_msgs_process = Process(target=self.handle_stm_messages)
            self.handle_commands_process = Process(target=self.handle_commands)

<<<<<<< HEAD
        if StartAndroid:
            self.handle_android_msgs_process.start()
            self.send_android_msgs_process.start()
=======
        self.handle_android_msgs_process.start()
        self.send_android_msgs_process.start()
>>>>>>> 2812027a3028b02e581981e7d1b9c117707d9a6b
        if StartSTM:
            self.handle_stm_msgs_process.start()
            self.handle_commands_process.start()

        logging.info("Processes started")

        if StartAndroid:
            self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_STATUS.value, 'Ready to start'))

    def terminate(self):
        self.android.disconnect()
        self.stm.disconnect()
        self.clear_queues()
        logging.info("Program terminated")

    def handle_android_messages(self):
        while True:
            try:
                msg_str = self.android.receive()
                recv_msg = json.loads(msg_str)
            except OSError:
                recv_msg = None
                logging.warning("Android connection dropped")

            if recv_msg is None:
                continue
            
            msg:AndroidMessage = json.loads(msg_str, object_hook=AndroidMessage.from_json)

            # add obstacles and calculate shortest path
            if msg.category == 'obstacles':
                # reset obstacles
                self.obstacles = []

                for ob in msg.value['obstacles']:
                    self.obstacles.append({
                        "x": ob['x'],
                        "y": ob['y'],
                        "d": ob['d'],
                        "id": ob['id'],
                    })
                
                self.find_shortest_path()

            elif msg.category == 'start':
                if self.command_queue.empty():
                    self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_STATUS.value, "No obstacles set"))
                    continue

                # reset gyroscope
                self.stm.send("RS00")

                # Enable movement
                self.start_movement.set()

                self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_STATUS.value, RobotStatus.READY))

            # manual control
            elif msg.category == 'control':
                try:
                    self.movement_lock.release()
                except ValueError:
                    logging.warning("movement lock is already released")

                self.movement_lock.acquire()
                self.clear_queues()

                command:str = msg.value['command']
                self.command_queue.put(command)
                self.translate_robot(command)
                self.path_queue.put(self.robot_location)

                self.movement_lock.release()
                      

    def send_android_messages(self):
        while True:
            try:
                if self.android_msgs.empty():
                    continue
                msg:AndroidMessage = self.android_msgs.get()
                logging.debug(f"msg:{msg}")
                self.android.send(msg)
            except queue.Empty:
                continue
            except OSError:
                pass
                #logging.warning("Android connection dropped")

    def handle_stm_messages(self):
        while True:
            msg:str = self.stm.receive()

            if msg is None:
                continue

            if not "ACK" in msg:
                logging.warning(f"Received unknown message from STM: {msg}")
                continue

            try:
                cur_location = self.path_queue.get_nowait()
                self.robot_location["x"] = cur_location["x"]
                self.robot_location["y"] = cur_location["y"]
                self.robot_location["d"] = cur_location["d"]
                
                self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_LOCATION.value, self.robot_location))
                
            except queue.Empty:
                continue
            except EOFError:
                continue
            except Exception as e:
                continue

<<<<<<< HEAD
=======
            self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_LOCATION.value, self.robot_location))
    
>>>>>>> 2812027a3028b02e581981e7d1b9c117707d9a6b
    def handle_commands(self):
        while True:
            try:
                command:str = self.command_queue.get()
                logging.debug(f"Command: {command}")
            except queue.Empty:
                continue
            except EOFError:
                continue

            # Wait until path has been calculated
            self.start_movement.wait()
            self.movement_lock.acquire()

            if command.startswith(stm_command_prefixes):
                logging.info("Inside send")
                self.stm.send(command)

            elif command.startswith("SNAP"):
                if command.find("_") == -1:
                    img_name = command[4:]
                else:
                    img_name = command[4:command.find("_")]

                self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_STATUS.value, RobotStatus.DETECTING_IMAGE))

                save_path = self.camera.capture(img_name)
                img_data = self.server.predict_image(save_path)
                
                self.android_msgs.put(AndroidMessage("image", {
                    "label": img_data['image_label'],
                    "id": img_data['image_id']
                }))

            elif command == "FIN":
                self.start_movement.clear()
                self.movement_lock.release()
                self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_STATUS.value, "Commands queue finished."))
                self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_STATUS.value, RobotStatus.FINISH))

            else:
                logging.warning(f"Unknown command: {command}")
            
            # release the lock after processing command
            self.movement_lock.release()

    def check_server(self):
        """
        Helper Function to ensure that server is running
        """
        try:
            status_code = self.server.server_status()
            if status_code == 200:
                logging.info("Server is running")
                return True
            return False

        except ConnectionError:
            logging.warning("Connection error to server")
            return False

        except requests.Timeout:
            logging.warning("Timed out waiting for response from server")
            return False

        except Exception as e:
            logging.warning(f"API error: {e}")
            return False

    def check_camera(self):
        """
        Helper Function to ensure that camera is working
        """
        try:
            save_path = self.camera.capture("test")
            os.remove(save_path)
            return True
        
        except Exception as e:
            logging.warning(f"Camera error: {e}")
            return False

    def find_shortest_path(self, robot_pos_x=1, robot_pos_y=1, robot_dir=0, retrying=False):
        """
        Sends a request to the server to find the shortest path and associated commands
        """
        self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_STATUS.value, RobotStatus.CALCULATING_PATH))

        data = {
            "obstacles": self.obstacles,
            "robot_pos_x": robot_pos_x,
            "robot_pos_y": robot_pos_y,
            "robot_dir": robot_dir,
            "retrying": retrying
        }

        res = requests.post(f"{server_url}:{server_port}/algo", json=data)

        if res.status_code != 200:
            self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_STATUS.value, f"There was an error when requesting to server. Status Code: {res.status_code}"))
            logging.warning(f"There was an error when requesting to server. Status Code: {res.status_code}")
            return
        
        res_data = res.json()
        path_data = res_data['data']
        
        if res_data['error']:
            self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_STATUS.value, f"Error when calculating shortest path: {res_data['error']}"))
            logging.warning(f"Error when calculating shortest path: {res_data['error']}")
            return

        # ignore first element as it is the starting position of the robot
        for location in path_data['path'][1:]:
            self.path_queue.put(location)
        
        for command in path_data['commands']:
            self.command_queue.put(command)

        self.android_msgs.put(AndroidMessage(BluetoothHeader.ROBOT_STATUS.value, "Retrieved shortest path from server. Robot is ready to move"))

    def translate_robot(self, command:str):
        """
        Translate the robot using the command given and updates its predicted location
        """
        if command.startswith("FW") or command.startswith("FS"):
            if self.robot_location['d'] == Direction.NORTH.value:
                self.robot_location['y'] += int(command[2:]) // 10
            elif self.robot_location['d'] == Direction.EAST.value:
                self.robot_location['x'] += int(command[2:]) // 10
            elif self.robot_location['d'] == Direction.SOUTH.value:
                self.robot_location['y'] -= int(command[2:]) // 10
            elif self.robot_location['d'] == Direction.WEST.value:
                self.robot_location['x'] -= int(command[2:]) // 10

        elif command.startswith("BW") or command.startswith("BS"):
            if self.robot_location['d'] == Direction.NORTH.value:
                self.robot_location['y'] -= int(command[2:]) // 10
            elif self.robot_location['d'] == Direction.EAST.value:
                self.robot_location['x'] -= int(command[2:]) // 10
            elif self.robot_location['d'] == Direction.SOUTH.value:
                self.robot_location['y'] += int(command[2:]) // 10
            elif self.robot_location['d'] == Direction.WEST.value:
                self.robot_location['x'] += int(command[2:]) // 10

        elif command.startswith("BR"):
            if self.robot_location['d'] == Direction.NORTH.value:
                self.robot_location['y'] += -3
                self.robot_location['x'] += 1
                self.robot_location['d'] = Direction.WEST.value
            elif self.robot_location['d'] == Direction.EAST.value:
                self.robot_location['y'] += -1
                self.robot_location['x'] += -3
                self.robot_location['d'] = Direction.NORTH.value
            elif self.robot_location['d'] == Direction.SOUTH.value:
                self.robot_location['y'] += 3
                self.robot_location['x'] += -1
                self.robot_location['d'] = Direction.EAST.value
            elif self.robot_location['d'] == Direction.WEST.value:
                self.robot_location['y'] += 1
                self.robot_location['x'] += 3
                self.robot_location['d'] = Direction.SOUTH.value

        elif command.startswith("BL"):
            if self.robot_location['d'] == Direction.NORTH.value:
                self.robot_location['y'] += -3
                self.robot_location['x'] += -1
                self.robot_location['d'] = Direction.EAST.value
            elif self.robot_location['d'] == Direction.EAST.value:
                self.robot_location['y'] += 1
                self.robot_location['x'] += -3
                self.robot_location['d'] = Direction.SOUTH.value
            elif self.robot_location['d'] == Direction.SOUTH.value:
                self.robot_location['y'] += 3
                self.robot_location['x'] += 1
                self.robot_location['d'] = Direction.WEST.value
            elif self.robot_location['d'] == Direction.WEST.value:
                self.robot_location['y'] += -1
                self.robot_location['x'] += 3
                self.robot_location['d'] = Direction.NORTH.value

        elif command.startswith("FL"):
            if self.robot_location['d'] == Direction.NORTH.value:
                self.robot_location['y'] += 3
                self.robot_location['x'] += -1
                self.robot_location['d'] = Direction.WEST.value
            elif self.robot_location['d'] == Direction.EAST.value:
                self.robot_location['y'] += -1
                self.robot_location['x'] += -3
                self.robot_location['d'] = Direction.SOUTH.value
            elif self.robot_location['d'] == Direction.SOUTH.value:
                self.robot_location['y'] += -3
                self.robot_location['x'] += 1
                self.robot_location['d'] = Direction.EAST.value
            elif self.robot_location['d'] == Direction.WEST.value:
                self.robot_location['y'] += -1
                self.robot_location['x'] += -3
                self.robot_location['d'] = Direction.SOUTH.value

        elif command.startswith("FR"):
            if self.robot_location['d'] == Direction.NORTH.value:
                self.robot_location['y'] += 3
                self.robot_location['x'] += 1
                self.robot_location['d'] = Direction.EAST.value
            elif self.robot_location['d'] == Direction.EAST.value:
                self.robot_location['y'] += 1
                self.robot_location['x'] += -3
                self.robot_location['d'] = Direction.NORTH.value
            elif self.robot_location['d'] == Direction.SOUTH.value:
                self.robot_location['y'] += -3
                self.robot_location['x'] += -1
                self.robot_location['d'] = Direction.WEST.value
            elif self.robot_location['d'] == Direction.WEST.value:
                self.robot_location['y'] += 1
                self.robot_location['x'] += -3
                self.robot_location['d'] = Direction.NORTH.value

    def clear_queues(self):
        """
        Helper Function to clear the queues
        """
        while not self.path_queue.empty():
            self.path_queue.get()
        
        while not self.command_queue.empty():
            self.command_queue.get()

        while not self.android_msgs.empty():
            self.android_msgs.get()

if __name__ == "__main__":
    rpi = RpiModule()
<<<<<<< HEAD
    rpi.initialize(CheckSvr=False, StartCamera=False, StartAndroid=False)
=======
    rpi.initialize(CheckSvr=False, StartCamera=False, StartSTM=False)
>>>>>>> 2812027a3028b02e581981e7d1b9c117707d9a6b
