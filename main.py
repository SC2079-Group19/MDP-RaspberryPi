StartAndroid    = False
StartSTM        = False
StartCamera     = True
CheckSvr        = True

Testing         = False

import json
import logging
import os
from multiprocessing import Process, Manager
import requests
import queue
import time

from config import stm_command_prefixes, server_url, server_port
from helper import RobotStatus, Direction
if StartAndroid:
    from Modules.AndroidModule import AndroidModule
from Modules.AndroidMessages import AndroidMessage, InfoMessage, RobotLocMessage, ImageMessage, BluetoothHeader
if StartCamera:
    from Modules.CameraModule import CameraModule

from Modules.StmModule import StmModule
from Modules.APIServer import APIServer

class RpiModule:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)

        if StartCamera:
            self.camera = CameraModule()
        if StartAndroid:
            self.android = AndroidModule()
        self.stm = StmModule()
        self.server = APIServer()

        self._manager = Manager()

        self.path_queue = self._manager.Queue()
        self.android_msgs = self._manager.Queue()
        self.android_dropped_event = self._manager.Event()
        self.command_queue = self._manager.Queue()

        self.movement_lock = self._manager.Lock()

        self.start_movement = self._manager.Event()

        self.obstacles = self._manager.list()
        self.robot_location = self._manager.dict()

        self.handle_android_msgs_process = None
        self.send_android_msgs_process = None
        self.handle_stm_msgs_process = None
        self.handle_commands_process = None

        self.robot_location["x"] = 1
        self.robot_location["y"] = 1
        self.robot_location["d"] = 0

    def initialize(self):
        if StartAndroid:
            self.android.connect()
        if StartSTM:
            if not self.stm.connect():
                logging.warning("[RpiModule.initialize]STM serial connection failed!")
                return False
        if CheckSvr:
            self.check_server()
        if StartCamera:
            self.check_camera()

        if StartAndroid:
            self.spawn_android_processes()
        if StartSTM:
            self.handle_stm_msgs_process = Process(target=self.handle_stm_messages)
            self.handle_commands_process = Process(target=self.handle_commands)
            self.handle_stm_msgs_process.start()
            self.handle_commands_process.start()

        if Testing:
            self.command_queue.put("SNAP1")
            self.command_queue.put("SNAP2")
            self.handle_commands_process = Process(target=self.handle_commands)
            self.handle_commands_process.start()
            self.start_movement.set()
            logging.info("[RpiModule.initialize]Testing Mode Started")

        logging.info("[RpiModule.initialize]Processes started")
        return True

    def EventLoop(self):
        try:
            if not StartAndroid:
                while True:
                    pass
            else:
                logging.info("[RpiModule.EventLoop]handle_android_drop_event")
                self.handle_android_drop_event()
        except KeyboardInterrupt:
            logging.info("[RpiModule.EventLoop]KeyboardInterrupt")
            self.terminate()

    def terminate(self):
        if StartAndroid:
            self.android.disconnect()
            self.handle_android_msgs_process.kill()
            self.send_android_msgs_process.kill()
            self.handle_android_msgs_process.join()
            self.send_android_msgs_process.join()
        if StartSTM:
            self.stm.disconnect()
            self.handle_stm_msgs_process.join()
            self.handle_commands_process.join()

        logging.info("[RpiModule.terminate]Processes joined")
        logging.info("[RpiModule.terminate]Program terminated")

    def handle_android_messages(self):
        while True:
            try:
                msg_str = self.android.receive()
                if msg_str is not None:
                    msg:AndroidMessage = json.loads(msg_str, object_hook=AndroidMessage.from_json)
            except OSError:
                logging.warning("[RpiModule.handle_android_messages]Android connection dropped")
                self.android_dropped_event.set()
            except json.decoder.JSONDecodeError:
                logging.warning("[RpiModule.handle_android_messages]Invalid json msg")

            if msg is None:
                continue
            # add obstacles and calculate shortest path
            if msg.category == BluetoothHeader.ITEM_LOCATION.value:
                # reset obstacles
                self.obstacles[:] = [] #has to clear it this way as its shared object

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
                    self.android_msgs.put(InfoMessage("No obstacles set"))
                    continue

                # reset gyroscope
                self.stm.send("RS00")

                # Enable movement
                self.start_movement.set()

                self.android_msgs.put(InfoMessage(RobotStatus.READY))

            # manual control
            elif msg.category == BluetoothHeader.ROBOT_CONTROL.value:
                try:
                    self.movement_lock.release()
                except:
                    logging.warning("[RpiModule.handle_android_messages]movement lock is already released")

                self.movement_lock.acquire()
                self.start_movement.set()
                self.clear_queues()

                command:str = msg.value
                self.command_queue.put(command)
                self.translate_robot(command)
                self.path_queue.put(self.robot_location)

                self.movement_lock.release()
                #self.start_movement.clear()
                      

    def send_android_messages(self):
        while True:
            try:
                if self.android_msgs.empty():
                    continue
                msg:AndroidMessage = self.android_msgs.get()
                logging.debug(f"[RpiModule.send_android_messages]msg:{msg}")
                self.android.send(msg)
            except queue.Empty:
                continue
            except OSError:
                self.android_dropped_event.set()
                logging.warning("[RpiModule.send_android_messages]Android connection dropped")

    def handle_stm_messages(self):
        while True:
            msg:str = self.stm.receive()

            if msg is None:
                continue

            if not "ACK" in msg or len(msg) <= 0:
                #logging.warning(f"[RpiModule.handle_stm_messages]Received unknown message from STM: {msg}, {type(msg)}")
                continue

            try:
                cur_location = self.path_queue.get_nowait()
                self.robot_location["x"] = cur_location["x"]
                self.robot_location["y"] = cur_location["y"]
                self.robot_location["d"] = cur_location["d"]
                
                self.android_msgs.put(RobotLocMessage(self.robot_location))
                
            except queue.Empty:
                continue
            except EOFError:
                continue
            except Exception as e:
                continue

    def handle_commands(self):
        while True:
            try:
                command:str = self.command_queue.get()
                logging.debug(f"[RpiModule.handle_commands]Command: {command}")
            except queue.Empty:
                continue
            except EOFError:
                continue

            # Wait until path has been calculated
            self.start_movement.wait()
            self.movement_lock.acquire()

            if command.startswith(stm_command_prefixes):
                #logging.info("[RpiModule.handle_commands]Inside send")
                self.stm.send(command)

            elif command.startswith("SNAP"):
                if command.find("_") == -1:
                    img_name = command[4:]
                else:
                    img_name = command[4:command.find("_")] + "_" + command[command.find('_')+1:]

                self.android_msgs.put(InfoMessage(RobotStatus.DETECTING_IMAGE))

                img_name = f"{time.time()}_{img_name}"
                save_path = self.camera.capture(img_name)
                img_data = self.server.predict_image(save_path)

                logging.info(f"[RpiModule.predict_image]Image data: {img_data}")
                
                self.android_msgs.put(AndroidMessage("image", {
                    "label": img_data['image_label'],
                    "id": img_data['image_id']
                }))

            elif command == "FIN":
                self.start_movement.clear()
                self.movement_lock.release()
                self.android_msgs.put(InfoMessage("Commands queue finished."))
                self.android_msgs.put(InfoMessage(RobotStatus.FINISH))

            else:
                logging.warning(f"[RpiModule.handle_commands]Unknown command: {command}")
            
            # release the lock after processing command
            self.movement_lock.release()

    def check_server(self):
        """
        Helper Function to ensure that server is running
        """
        try:
            status_code = self.server.server_status()
            if status_code == 200:
                logging.info("[RpiModule.check_server]Server is running")
                return True
            return False

        except ConnectionError:
            logging.warning("[RpiModule.check_server]Connection error to server")
            return False

        except requests.Timeout:
            logging.warning("[RpiModule.check_server]Timed out waiting for response from server")
            return False

        except Exception as e:
            logging.warning(f"[RpiModule.check_server]API error: {e}")
            return False

    def check_camera(self):
        """
        Helper Function to ensure that camera is working
        """
        try:
            save_path = self.camera.capture("test")
            os.remove(save_path)
            logging.info("[RpiModule.check_camera]Camera is running")
            return True
        
        except Exception as e:
            logging.warning(f"[RpiModule.check_camera]Camera error: {e}")
            return False

    def find_shortest_path(self, robot_pos_x=1, robot_pos_y=1, robot_dir=0, retrying=False):
        """
        Sends a request to the server to find the shortest path and associated commands
        """
        self.android_msgs.put(InfoMessage(RobotStatus.CALCULATING_PATH))

        data = {
            "obstacles": self.obstacles,
            "robot_pos_x": robot_pos_x,
            "robot_pos_y": robot_pos_y,
            "robot_dir": robot_dir,
            "retrying": retrying
        }

        res = requests.post(f"{server_url}:{server_port}/algo", json=data)

        if res.status_code != 200:
            self.android_msgs.put(InfoMessage(f"There was an error when requesting to server. Status Code: {res.status_code}"))
            logging.warning(f"[RpiModule.find_shortest_path]There was an error when requesting to server. Status Code: {res.status_code}")
            return
        
        res_data = res.json()
        path_data = res_data['data']
        
        if res_data['error']:
            self.android_msgs.put(InfoMessage(f"Error when calculating shortest path: {res_data['error']}"))
            logging.warning(f"[RpiModule.find_shortest_path]Error when calculating shortest path: {res_data['error']}")
            return

        # ignore first element as it is the starting position of the robot
        for location in path_data['path'][1:]:
            self.path_queue.put(location)
        
        for command in path_data['commands']:
            self.command_queue.put(command)

        self.android_msgs.put(InfoMessage("Retrieved shortest path from server. Robot is ready to move"))

    def translate_robot(self, command:str):
        """
        Translate the robot using the command given and updates its predicted location
        """
        if len(command) < 4:
            logging.debug("[RpiModule.translate_robot]Invalid command from android")
            return
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

    def spawn_android_processes(self):
        self.handle_android_msgs_process = Process(target=self.handle_android_messages)
        self.send_android_msgs_process = Process(target=self.send_android_messages)

        self.handle_android_msgs_process.start()
        self.send_android_msgs_process.start()
        self.android_msgs.put(InfoMessage('Ready to start'))

    def handle_android_drop_event(self):
        while True:
            self.android_dropped_event.wait()
            
            logging.debug('[RpiModule.handle_android_drop_event]Killing android process')
            self.handle_android_msgs_process.kill()
            self.send_android_msgs_process.kill()

            self.handle_android_msgs_process.join()
            self.send_android_msgs_process.join()
            logging.debug('[RpiModule.handle_android_drop_event]Android processes killed')

            self.android.disconnect()
            self.android.connect()

            self.spawn_android_processes()
            self.android_dropped_event.clear()


if __name__ == "__main__":
    rpi = RpiModule()
    if rpi.initialize():
        rpi.EventLoop()
