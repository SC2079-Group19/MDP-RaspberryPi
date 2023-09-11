import logging
import serial

from config import serial_port, baud_rate, stm_message_len

class StmModule:
    def __init__(self):
        self.serial = None

    def connect(self):
        try:
            self.serial = serial.Serial(serial_port, baud_rate, timeout=2.0)
            logging.info("[StmModule]Connected to STM")
            return True
        except Exception as e:
            logging.warning(f"[StmModule]Error when connecting to STM: {e}")
            return False
       
    def disconnect(self):
        try:
            if self.serial is not None:
                self.serial.close()
                self.serial = None
            logging.info("[StmModule]Disconnected from STM")

        except Exception as e:
            logging.warning(f"[StmModule]Error when disconnecting from STM: {e}")

    def send(self, msg:str):
        raw_byte = msg.encode("utf-8")
        if len(raw_byte) < stm_message_len:
            for x in range(len(raw_byte) - stm_message_len):
                raw_byte.append(0)

        self.serial.write(raw_byte)
        logging.debug(f"[StmModule]Sent message to STM: {msg} : {raw_byte}")

    def receive(self):
        msg = self.serial.readline().decode("utf-8")
        if len(msg) > 0:
            logging.debug(f"[StmModule]Received message from STM: {msg}")
        return msg

if __name__ == "__main__":
    pass
