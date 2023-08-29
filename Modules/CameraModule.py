import logging
import os
from time import sleep
from picamera import PiCamera

from config import resolution, warmup_time

class CameraModule:
    def __init__(self):
        self._camera = PiCamera()
        self._resolution = resolution
        self._save_folder = "images"
        self._warmup_time = warmup_time
        
        logging.info(f"Camera Module initialized with {self._resolution} resolution and " + 
                f"{self._warmup_time}s warm up time")

    @property
    def resolution(self):
        return self._resolution

    def capture(self, name:str):
        self._camera.start_preview()
        sleep(self._warmup_time)

        if not os.path.exists(self._save_folder):
            os.makedirs(self._save_folder)

        save_path = os.path.join(self._save_folder, name+".jpg")
        self._camera.capture(save_path)
        logging.info(f"Saved image to {save_path}")

        return save_path

if __name__ == "__main__":
    pass

