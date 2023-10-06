import bluetooth as bt
import logging
import os
import socket

from config import uuid,service_name
from Modules.AndroidMessages import AndroidMessage
from utils import CreateColouredLogging

class AndroidModule:
    def __init__(self):
        self.client_sock = None
        self.server_sock = None
        #self.logger = CreateColouredLogging(__name__)

    def connect(self):
        logging.info("[AndroidModule]Bluetooth connection started")
        try:
            os.system("sudo hciconfig hci0 piscan")

            self.server_sock = bt.BluetoothSocket(bt.RFCOMM)
            self.server_sock.bind(("", bt.PORT_ANY))
            self.server_sock.listen(1)

            port = self.server_sock.getsockname()[1]

            bt.advertise_service(self.server_sock, service_name, 
                                service_id=uuid,
                                service_classes=[uuid, bt.SERIAL_PORT_CLASS],
                                profiles=[bt.SERIAL_PORT_PROFILE])
           
            logging.info(f"[AndroidModule]Awaiting bluetooth connection on RFCOMM CHANNEL {port}")
            self.client_sock, client_info = self.server_sock.accept()
            logging.info(f"[AndroidModule]Accepted connection from {client_info}")

        except Exception as e:
            logging.warning(f"Error in establishing bluetooth connection: {e}")
            if self.server_sock is not None:
                self.server_sock.close()
                self.server_sock = None
            if self.client_sock is not None:
                self.client_sock.close()
                self.client_sock = None

    def disconnect(self):
        try:
            logging.info("[AndroidModule]Disconnecting bluetooth link")
            if self.server_sock is not None:
                self.server_sock.shutdown(socket.SHUT_RDWR)
                self.server_sock.close()
                self.server_sock = None
            if self.client_sock is not None:
                self.client_sock.shutdown(socket.SHUT_RDWR)
                self.client_sock.close()
                self.server_sock = None
            logging.info("[AndroidModule]Disconnected bluetooth link")

        except Exception as e:
            logging.warning(f"[AndroidModule]Error when disconnecting bluetooth link: {e}")

    def send(self, message:AndroidMessage):
        try:
            #if len(msg) < 512:
            #for x in range(stm_message_len - len(msg)):
                #msg += ' '
            #raw_byte = (msg).encode("utf-8")
            self.client_sock.send(f"{message.json}\n".encode("utf-8"))
            logging.debug(f"[AndroidModule]Sent message to android: {message.json}")
        
        except Exception as e:
            logging.warning(f"[AndroidModule]Error when sending message to android: {e} : {type(e)}")
            raise e

    def receive(self):
        try:
            encoded_msg = self.client_sock.recv(1024)
            msg = encoded_msg.decode("utf-8")
            #msg = msg.replace("\"", "'")
            logging.debug(f"[AndroidModule]Received message from android: {msg}")
            return msg

        except Exception as e:
            logging.warning(f"[AndroidModule]Error when receiving message from android: {e}")
            raise e


if __name__ == "__main__":
    pass
