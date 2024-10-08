StartAndroid    = True
StartSTM        = True
StartCamera     = True
CheckSvr        = True

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
from Modules.AndroidMessages import AndroidMessage, InfoMessage, RobotLocMessage, \
    ImageMessage, BluetoothHeader
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

        self.obstacles = self._manager.list()
        self.robot_location = self._manager.dict()

        self.handle_android_msgs_process = None
        self.send_android_msgs_process = None
        self.handle_stm_msgs_process = None
        self.handle_commands_process = None

        self.robot_location["x"] = 1
        self.robot_location["y"] = 1
        self.robot_location["d"] = 0

        self.ack_count = 0
        self.near_flag = self._manager.Event()
        self.second_direction = None


    def initialize(self):
        if StartAndroid:
            self.android.connect()
        if StartSTM:
            if not self.stm.connect():
                logging.warning("[RpiModule.initialize]STM serial connection failed!")
                return False
        if CheckSvr:
            self.check_server()
        #if StartCamera:
            #self.check_camera()

        if StartAndroid:
            self.spawn_android_processes()
        if StartSTM:
            self.handle_stm_msgs_process = Process(target=self.handle_stm_messages)
            self.handle_commands_process = Process(target=self.handle_commands)
            self.handle_stm_msgs_process.start()
            self.handle_commands_process.start()

        logging.info("[RpiModule.initialize]Processes started")
        return True

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
            logging.debug(f"[RpiModule.handle_android_messages]msg.value: {msg.value}")

            if msg.category == BluetoothHeader.START_MOVEMENT.value:
                if not self.check_server():
                    logging.error("[RpiModule.handle_android_messages]Start Command Aborted")
                    continue

                logging.info("[RpiModule.handle_android_messages]Start command received")

                self.clear_queues()
                
                # To reset gyroscope
                #self.command_queue.put("RS00") # ack_count = 1

                # Try to identify direction before moving
                img_name = f"{time.time()}_first_far"
                save_path = self.camera.capture(img_name)
                img_data = self.server.predict_image(save_path)

                # To move until obstacle is reached
                self.command_queue.put("DT30") # ack_count = 2
                
                if img_data["image_label"] == "Left":
                    self.command_queue.put("FL00") # ack_count = 3
                    self.command_queue.put("FR00") # ack_count = 4
                    self.command_queue.put("FW10") # ack_count = 5
                elif img_data["image_label"] == "Right":
                    self.command_queue.put("FR00") # ack_count = 3
                    self.command_queue.put("FL00") # ack_count = 4
                    self.command_queue.put("FW10") # ack_count = 5
                else:
                    self.near_flag.set() # need to take again when closer to image

                self.android_msgs.put(InfoMessage("Processed Start Command"))

    def handle_stm_messages(self):
        while True:
            msg:str = self.stm.receive()

            if msg is None:
                continue

            if not "ACK" in msg or len(msg) <= 0:
                continue
            
            self.ack_count += 1
            logging.debug(f"[RpiModule.handle_stm_messages]ACK count: {self.ack_count}")

            try:
                self.movement_lock.release()
            except Exception:
                logging.warning("[RpiModule.handle_stm_messages]Tried to release a released lock!")

            if self.ack_count == 2: # Robot reached first obstacle
                if self.near_flag.is_set(): # need to take image again
                    img_name = f"{time.time()}_first_near"
                    save_path = self.camera.capture(img_name)
                    img_data = self.server.predict_image(save_path)

                    if img_data["image_label"] == "Left":
                        self.command_queue.put("FL00") # ack_count = 3
                        self.command_queue.put("FR00") # ack_count = 4
                        self.command_queue.put("FW10") # ack_count = 5
                    # By default, go right
                    else:
                        self.command_queue.put("FR00") # ack_count = 3
                        self.command_queue.put("FL00") # ack_count = 4
                        self.command_queue.put("FW10") # ack_count = 5

                    self.near_flag.clear() # resets the near_flag

            if self.ack_count == 5:  # Robot crossed first obstacle
                img_name = f"{time.time()}_second_far"
                save_path = self.camera.capture(img_name)
                img_data = self.server.predict_image(save_path)

                # To move until obstacle is reached
                self.command_queue.put("DT10") # ack_count = 6

                if img_data["image_label"] == "Left":
                    self.command_queue.put("FL00") # ack_count = 7
                    self.command_queue.put("FW30") # ack_count = 8
                    self.command_queue.put("FR00") # ack_count = 9
                    self.command_queue.put("FW10") # ack_count = 10
                    self.second_direction = img_data["image_label"]
                elif img_data["image_label"] == "Right":
                    self.command_queue.put("FR00") # ack_count = 7
                    self.command_queue.put("FW30") # ack_count = 8
                    self.command_queue.put("FL00") # ack_count = 9
                    self.command_queue.put("FW10") # ack_count = 10
                    self.second_direction = img_data["image_label"]
                else:
                    self.near_flag.set() # need to take again when closer to image

            elif self.ack_count == 6: # Robot reached second obstacle
                if self.near_flag.is_set(): # need to take image again
                    img_name = f"{time.time()}_second_near"
                    save_path = self.camera.capture(img_name)
                    img_data = self.server.predict_image(save_path)

                    if img_data["image_label"] == "Left":
                        self.command_queue.put("FL00") # ack_count = 7
                        self.command_queue.put("FW30") # ack_count = 8
                        self.command_queue.put("FR00") # ack_count = 9
                        self.command_queue.put("FW10") # ack_count = 10
                    # By default, go right
                    else:
                        self.command_queue.put("FR00") # ack_count = 7
                        self.command_queue.put("FW30") # ack_count = 8
                        self.command_queue.put("FL00") # ack_count = 9
                        self.command_queue.put("FW10") # ack_count = 10

                    self.second_direction = img_data["image_label"]

                    self.near_flag.clear() # resets the near_flag
            
            elif self.ack_count == 10: # Robot crossed second obstacle
                if self.second_direction == "Left":
                    self.command_queue.put("FR00")
                    self.command_queue.put("FW60")
                    self.command_queue.put("FR00")
                    # Move until right side barrier of parking lot
                    self.command_queue.put("DT10")
                    self.command_queue.put("FR00")
                    self.command_queue.put("FL00")
                    # Move until inside parking lot
                    self.command_queue.put("DT10")
                    self.command_queue.put("FIN")
                
                else:
                    self.command_queue.put("FL00")
                    self.command_queue.put("FW60")
                    self.command_queue.put("FL00")
                    # Move until right side barrier of parking lot
                    self.command_queue.put("DT10")
                    self.command_queue.put("FL00")
                    self.command_queue.put("FR00")
                    # Move until inside parking lot
                    self.command_queue.put("DT10")
                    self.command_queue.put("FIN")

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
            logging.debug("[RpiModule.handle_commands]Waiting for movement_lock")
            self.movement_lock.acquire()

            if command.startswith(stm_command_prefixes):
                #logging.info("[RpiModule.handle_commands]Inside send")
                self.stm.send(command)

            elif command == "FIN":
                self.start_movement.clear()
                self.movement_lock.release()
                self.android_msgs.put(InfoMessage("Commands queue finished."))
                self.android_msgs.put(InfoMessage(RobotStatus.FINISH))

            else:
                logging.warning(f"[RpiModule.handle_commands]Unknown command: {command}")
            
            # release the lock after processing command
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
            res = self.android_dropped_event.wait(1)
            if not res:
                self.check_processes_if_running()
                continue
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
