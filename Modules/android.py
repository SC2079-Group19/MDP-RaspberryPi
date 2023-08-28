import bluetooth as bt
import json
import os
import socket

from config import uuid

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
    def json(self):
        return json.dumps({ "category": self._category, "value": self._value })

class AndroidLink:
    def __init__(self):
        self.client_sock = None
        self.server_sock = None

    def connect(self):
        print("Bluetooth connection started")
        try:
            os.system("sudo hciconfig hci0 piscan")

            self.server_sock = bt.BluetoothSocket(bt.RFCOMM)
            self.server_sock.bind(("", bt.PORT_ANY))
            self.server_sock.listen(1)

            port = self.server_sock.getsockname()[1]

            bt.advertise_service(self.server_sock, "MDP-Group19-RPi", 
                                service_id=uuid,
                                service_classes=[uuid, bt.SERIAL_PORT_CLASS],
                                profiles=[bt.SERIAL_PORT_PROFILE])
           
            print(f"Awaiting bluetooth connection on RFCOMM CHANNEL {port}")
            self.client_sock, client_info = self.server_sock.accept()
            print(f"Accepted connection from {client_info}")

        except Exception as e:
            print(f"Error in establishing bluetooth connection: {e}")
            if self.server_sock is not None:
                self.server_sock.close()
                self.server_sock = None
            if self.client_sock is not None:
                self.client_sock.close()
                self.client_sock = None

    def disconnect(self):
        try:
            print("Disconnecting bluetooth link")
            if self.server_sock is not None:
                self.server_sock.shutdown(socket.SHUT_DOWN)
                self.server_sock.close()
                self.server_sock = None
            if self.client_sock is not None:
                self.client_sock.shutdown(socket.SHUT_DOWN)
                self.client_sock.close()
                self.server_sock = None
            print("Disconnected bluetooth link")

        except Exception as e:
            print(f"Error when disconnecting bluetooth link: {e}")

    def send(self, message:AndroidMessage):
        try:
            self.client_sock.send(f"{message.json}\n".encode("utf-8"))
        
        except Exception as e:
            print(f"Error when sending message to andriod: {e}")
            raise e

    def receive(self):
        try:
            encoded_msg = self.client_sock.recv(1024)
            msg = encoded_msg.decode("utf-8")
            return msg

        except Exception as e:
            print(f"Error when receiving message from andriod: {e}")
            raise e


