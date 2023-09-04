import bluetooth as bt
import json
import logging
import os
import socket

from config import uuid,service_name

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

class AndroidModule:
    def __init__(self):
        self.client_sock = None
        self.server_sock = None

    def connect(self):
        logging.info("Bluetooth connection started")
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
           
            logging.info(f"Awaiting bluetooth connection on RFCOMM CHANNEL {port}")
            self.client_sock, client_info = self.server_sock.accept()
            logging.info(f"Accepted connection from {client_info}")

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
            logging.info("Disconnecting bluetooth link")
            if self.server_sock is not None:
                self.server_sock.shutdown(socket.SHUT_DOWN)
                self.server_sock.close()
                self.server_sock = None
            if self.client_sock is not None:
                self.client_sock.shutdown(socket.SHUT_DOWN)
                self.client_sock.close()
                self.server_sock = None
            logging.info("Disconnected bluetooth link")

        except Exception as e:
            logging.warning(f"Error when disconnecting bluetooth link: {e}")

    def send(self, message:AndroidMessage):
        try:
            self.client_sock.send(f"{message.json}\n".encode("utf-8"))
            logging.debug(f"Sent message to android: {message.json}")
        
        except Exception as e:
            logging.warning(f"Error when sending message to andriod: {e} : {type(e)}")
            raise e

    def receive(self):
        try:
            encoded_msg = self.client_sock.recv(1024)
            msg = encoded_msg.decode("utf-8")
            logging.debug(f"Received message from android: {msg}")
            return msg

        except Exception as e:
            logging.warning(f"Error when receiving message from andriod: {e} : {type(e)}")
            raise e


if __name__ == "__main__":
    pass
