from datetime import datetime
import json
import logging
from multiprocessing import Process, Manager
from requests import Timeout

from config import stm_command_prefixes
from Modules.AndroidModule import AndroidModule, AndroidMessage
from Modules.CameraModule import CameraModule
from Modules.StmModule import StmModule
from Modules.APIServer import APIServer

def InitializeCamera():
    cm = CameraModule()
    return cm

def InitializeAndroid():
    android_link = AndroidModule()
    android_link.connect()
    return android_link

def InitializeStm():
    stm = StmModule()
    stm.connect()
    return stm

def InitializeImageRec():
    img_rec = ImageRecModule()
    return img_rec

class RpiModule:
    def __init__(self):
        self._camera = CameraModule()
        self._android = AndroidModule()
        self._stm = StmModule()
        self._server = APIServer()

        self._manager = Manager()

        self._path = self._manager.Queue()
        self._android_msgs = self._manager.Queue()
        self._commands = self._manager.Queue()

    def initialize(self):
        self._android.connect()
        self._stm.connect()
        self.check_server()
        self.check_camera()

        self.handle_android_msgs_process = Process(target=self.handle_android_messages)
        self.send_android_msgs_process = Process(target=self.send_android_messages)
        self.handle_stm_msgs_process = Process(target=self.handle_stm_messages)
        self.handle_commands_process = Process(target=self.handle_commands)

    def terminate(self):
        self._android.disconnect()
        self._stm.disconnect()
        logging.info("Program terminated")

    def handle_android_messages(self):
        while True:
            try:
                recv_msg = json.loads(self._android.receive())
            except OSError:
                recv_msg = None
                logging.warning("Android connection dropped")

            if recv_msg is None:
                continue
            
            # TO DO: HANDLE ANDROID MESSAGES

    def send_android_messages(self):
        while True:
            if self._android_msgs.empty():
                continue

            msg:AndroidMessage = self._android_msgs.get(timeout=0.5)
            
            try:
                self._android.send(msg)
            except OSError:
                logger.warning("Android connection dropped")

    def handle_stm_messages(self):
        while True:
            msg = self._stm.receive()

            if msg != "ACK":
                logging.warning(f"Received unknown message from STM: {msg}")
                continue

            # TO DO: HANDLE STM MESSAGES
    
    def handle_commands(self):
        while True:
            command = self._commands.get()
            logging.debug(f"Command: {command}")

            if command.startswith(stm_command_prefixes):
                self._stm.send(command)

            elif command.startswith("SNAP"):
                img_name = datetime.now().strftime("%d/%m/%Y-%H:%M:%S")
                save_path = self._camera.capture(img_name)
                img_data = self._server.predict_image(save_path)

            else:
                logging.warning("Unknown command: {command}")

    def check_server(self):
        """
        Helper Function to ensure that server is running
        """
        try:
            status_code = self._server.server_status()
            if status_code == 200:
                logging.info("Server is running")
                return True
            return False

        except ConnectionError:
            logging.warning("Connection error to server")
            return False

        except Timeout:
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
            save_path = self._camera.capture("test")
            os.remove(save_path)
            return True
        
        except Exception as e:
            logging.warning(f"Camera error: {e}")
            return False

if __name__ == "__main__":
    camera = InitializeCamera()
    android = InitializeAndroid()
    stm = InitializeStm()
    img_rec = InitializeImageRec()
