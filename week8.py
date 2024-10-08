StartAndroid    = True
StartSTM        = True
StartCamera     = True
CheckSvr        = True

import ast
import json
import logging
import os
from multiprocessing import Process, Manager
import requests
import queue
import time

from config import stm_command_prefixes, server_url, server_port
from helper import RobotStatus, Direction, TranslateCommand
if StartAndroid:
    from Modules.AndroidModule import AndroidModule
from Modules.AndroidMessages import AndroidMessage, InfoMessage, RobotLocMessage, \
    ImageMessage, BluetoothHeader, StatusMessage
if StartCamera:
    from Modules.CameraModule import CameraModule

from Modules.StmModule import StmModule
from Modules.APIServer import APIServer
from utils import local_StreamHandler

class RpiModule:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG, handlers=[local_StreamHandler])

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
        self.manual_ctrl = self._manager.Event()
        self.empty = self._manager.Event()
        self.full = self._manager.Event()

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

        if StartAndroid:
            self.spawn_android_processes()
        if StartSTM:
            self.handle_stm_msgs_process = Process(target=self.handle_stm_messages)
            self.handle_commands_process = Process(target=self.handle_commands)
            self.handle_stm_msgs_process.start()
            self.handle_commands_process.start()

        logging.info("[RpiModule.initialize]Processes started")
        return True

    def EventLoop(self):
        try:
            if not StartAndroid:
                while True:
                    self.check_processes_if_running()
            else:
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
            msg = None
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
            logging.debug(f"[RpiModule.handle_android_messages]msg.value: {msg.value}")

            # add obstacles and calculate shortest path
            if msg.category == BluetoothHeader.ITEM_LOCATION.value:
                # reset obstacles
                self.obstacles[:] = [] #has to clear it this way as its shared object

                obstacles = ast.literal_eval(msg.value)  
                logging.debug(f'[RpiModule.handle_android_messages]data_list = {obstacles}')
                logging.debug(f'[RpiModule.handle_android_messages]data_list type = {type(obstacles)}')

                for ob in obstacles:
                    self.obstacles.append({
                        "x": ob['x'],
                        "y": ob['y'],
                        "d": int(ob['d']),
                        "id": ob['id'],
                    })
                
                self.find_shortest_path(retrying=False, bull=False)

            elif msg.category == BluetoothHeader.ROBOT_LOCATION.value:
                data_dict = json.loads(msg.value)
                logging.debug(f'[RpiModule.handle_android_messages]msg.value = {msg.value}')

                self.robot_location["x"] = data_dict['x']
                self.robot_location["y"] = data_dict['y']
                self.robot_location["d"] = data_dict['d']

                logging.debug(f"[RpiModule.handle_android_messages]New Robot Location - x: {self.robot_location['x']}, y: {self.robot_location['y']}, d: {self.robot_location['d']}")

            elif msg.category == BluetoothHeader.START_MOVEMENT.value:
                if self.command_queue.empty():
                    self.android_msgs.put(InfoMessage("No obstacles set"))
                    continue

                # reset gyroscope
                # self.stm.send("RS00")

                # Enable movement
                self.start_movement.set()
                self.full.set()

                self.android_msgs.put(StatusMessage(RobotStatus.READY))

            # manual control
            elif msg.category == BluetoothHeader.ROBOT_CONTROL.value:
                try:
                    self.movement_lock.release()
                except:
                    logging.warning("[RpiModule.handle_android_messages]movement lock is already released")

                self.movement_lock.acquire()
                
                self.clear_queues()
                command:str = msg.value
                self.command_queue.put(command)
                self.translate_robot(command)
                self.path_queue.put(self.robot_location)

                self.start_movement.set()
                self.manual_ctrl.set()
                self.full.set()
                self.movement_lock.release()
                      
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
                continue

            try:
                # Movement Lock is needed to prevent further commands sent to stm
                logging.debug("[RpiModule.handle_stm_messages]Waiting for empty")
                self.empty.wait()
                logging.debug("[RpiModule.handle_stm_messages]Waiting for movement_lock")
                self.movement_lock.acquire()
                logging.debug("[RpiModule.handle_stm_messages]Waiting for path_queue")
                try:
                    cur_location = self.path_queue.get_nowait()
                    self.robot_location["x"] = cur_location["x"]
                    self.robot_location["y"] = cur_location["y"]

                    # Sanity check
                    if cur_location['d'] >= 360:
                        cur_location['d'] = cur_location['d'] % 360
                    while cur_location['d'] < 0:
                        cur_location['d'] += 360
                    self.robot_location["d"] = cur_location["d"]

                    self.UpdateAndroidRobotLocation()
                except Exception:
                    logging.warning("Path queue is empty!")
                # Allow further actions to be sent to stm
                self.empty.clear()
                self.full.set()
                self.movement_lock.release()
            except queue.Empty:
                continue
            except Exception:
                continue
    
    def UpdateAndroidRobotLocation(self):
        self.android_msgs.put(RobotLocMessage(self.robot_location))

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
            logging.debug("[RpiModule.handle_commands]Waiting for start_movement")
            self.start_movement.wait()

            # Movement Lock is needed to move and take pictures
            logging.debug("[RpiModule.handle_commands]Waiting for full")
            self.full.wait()
            logging.debug("[RpiModule.handle_commands]Waiting for movement_lock")
            self.movement_lock.acquire()

            if command.startswith(stm_command_prefixes):
                self.stm.send(command)
                self.full.clear()
                self.empty.set()
                self.movement_lock.release()

            elif command.startswith("SNAP"):
                if command.find("_") == -1:
                    img_name = command[4:]
                else:
                    img_name = command[4:command.find("_")] + "_" + command[command.find('_')+1:]
                
                logging.info(f"[RpiModule.predict_image]Image Name: {img_name}")
                self.android_msgs.put(StatusMessage(RobotStatus.DETECTING_IMAGE))
                logging.info(f"[RpiModule.predict_image]After send status")
                img_name = f"{time.time()}_{img_name}"
                save_path = self.camera.capture(img_name)
                self.android_msgs.put(InfoMessage("Captured image, sending to server"))
                logging.info(f"[RpiModule.predict_image]After capture")
                img_data = self.server.predict_image(save_path)
                self.android_msgs.put(InfoMessage("Received image result"))
                logging.info(f"[RpiModule.predict_image]Image data: {img_data}")

                if img_data is not None:
                    self.android_msgs.put(AndroidMessage(BluetoothHeader.IMAGE_RESULT.value, str({
                        "target_id": int(img_data['image_id']),
                        "obstacle_id": int(img_data['obstacle_id'])
                    })))

                # self.full.clear()
                self.empty.set()
                self.movement_lock.release()

            elif command == "FIN":
                self.start_movement.clear()
                # self.empty.clear()
                # self.movement_lock.release()
                # self.full.clear()
                self.server.stitch_images()
                self.android_msgs.put(InfoMessage("Commands queue finished."))
                self.android_msgs.put(StatusMessage(RobotStatus.FINISH))

            else:
                logging.warning(f"[RpiModule.handle_commands]Unknown command: {command}")
            if self.manual_ctrl.is_set():
                self.manual_ctrl.clear()
                self.start_movement.clear()

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

    def find_shortest_path(self, robot_pos_x=1, robot_pos_y=1, robot_dir=0, retrying=False, bull=False):
        """
        Sends a request to the server to find the shortest path and associated commands
        """
        self.android_msgs.put(StatusMessage(RobotStatus.CALCULATING_PATH))
        logging.debug('[RpiModule.find_shortest_path]Finding path')
        data = {
            "obstacles": list(self.obstacles),
            "robot_pos_x": robot_pos_x,
            "robot_pos_y": robot_pos_y,
            "robot_dir": robot_dir,
            "retrying": retrying,
            "bull": bull
        }
        path_data = self.server.query_path(data)

        if path_data is None:
            self.android_msgs.put(InfoMessage(f"There was an error when querying path"))

        else:
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
        dx, dy, direction = TranslateCommand(command, self.robot_location['d'])
        self.robot_location['x'] += dx
        self.robot_location['y'] += dy
        self.robot_location['d'] = direction

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
        self.UpdateAndroidRobotLocation()

    def handle_android_drop_event(self):
        while True:
            res = self.android_dropped_event.wait(1)
            if not res:
                self.check_processes_if_running()
                continue

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

    def check_processes_if_running(self):
        if StartSTM:
            if not self.handle_commands_process.is_alive():
                logging.debug('[RpiModule.check_processes_if_running]handle_commands_process might have crashed, restarting')
                self.handle_commands_process.join()
                self.handle_commands_process = Process(target=self.handle_commands)
                self.handle_commands_process.start()
        
            if not self.handle_stm_msgs_process.is_alive():
                logging.debug('[RpiModule.check_processes_if_running]handle_stm_msgs_process might have crashed, restarting')
                self.handle_stm_msgs_process.join()
                self.handle_stm_msgs_process = Process(target=self.handle_stm_messages)
                self.handle_stm_msgs_process.start()
        if StartAndroid:
            if not self.handle_android_msgs_process.is_alive():
                logging.debug('[RpiModule.check_processes_if_running]handle_android_msgs_process might have crashed, restarting')
                self.handle_android_msgs_process.join()
                self.handle_android_msgs_process = Process(target=self.handle_android_messages)
                self.handle_android_msgs_process.start()
        
if __name__ == "__main__":
    rpi = RpiModule()
    if rpi.initialize():
        rpi.EventLoop()
