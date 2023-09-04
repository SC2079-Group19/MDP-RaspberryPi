import logging
import serial

from config import serial_port, baud_rate

class StmModule:
    def __init__(self):
        self.serial = None

    def connect(self):
        try:
            self.serial = serial.Serial(serial_port, baud_rate, timeout=2.0)
            logging.info("Connected to STM")

        except Exception as e:
            logging.warning(f"Error when connecting to STM: {e}")
            raise e
       
    def disconnect(self):
        try:
            if self.serial is not None:
                self.serial.close()
                self.serial = None
            logging.info("Disconnected from STM")

        except Exception as e:
            logging.warning(f"Error when disconnecting from STM: {e}")

    def send(self, msg:str):
        self.serial.write(msg.encode("utf-8"))
        logging.debug(f"Sent message to STM: {msg}")

    def receive(self):
        msg = self.serial.readline().decode("utf-8").strip()
        logging.debug(f"Received message from STM: {msg}")
        return msg

if __name__ == "__main__":
    pass
