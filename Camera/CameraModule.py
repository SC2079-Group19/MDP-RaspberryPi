import os
from time import sleep
from picamera import PiCamera

class CameraModule:
    def __init__(self):
        self.camera = PiCamera()
        self.camera.resolution = (1024, 768)
        self.save_folder = "images"
    
    def capture(self, name, warm_up=2):
        self.camera.start_preview()
        sleep(warm_up)

        if not os.path.exists(self.save_folder):
            os.makedirs(self.save_folder)
        save_path = os.path.join(self.save_folder, name+".jpg")
        self.camera.capture(save_path)

if __name__ == "__main__":
    cm = CameraModule()
    cm.capture("test")


