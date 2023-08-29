import serial

from config import serial_port, baud_rate

class StmModule:
    def __init__(self):
        self.serial = None

    def connect(self):
        self.serial = serial.Serial(serial_port, baud_rate, timeout=2.0)
        print("Connected to STM")
       
    def disconnect(self):
        if self.serial is not None:
            self.serial.close()
            self.serial = None
        print("Disconnected from STM")

    def send(self, msg:str):
        self.serial.write(msg.encode("utf-8"))

    def receive(self):
        msg = self.serial.readline().decode("utf-8")
        return msg

if __name__ == "__main__":
    pass
