import logging
import os
from time import sleep
from picamera import PiCamera

from config import resolution, warmup_time

"""
> .Capture method creates a PiCamera object, this object belongs to the caller thread
> If any other thread happens to call capture, there will be a deadlock as PiCamera object creation
> will try to get ownership from the other thread
"""
class CameraModule:
    def __init__(self):
        self._save_folder = "./images/"
        self._warmup_time = warmup_time
        
        logging.info(f"[CameraModule]Camera Module initialized with {resolution} resolution and " + 
                f"{self._warmup_time}s warm up time")

    def capture(self, name:str):
        camera = PiCamera()
        camera.resolution = resolution
        # sleep(self._warmup_time)

        if not os.path.exists(self._save_folder):
            os.makedirs(self._save_folder)

        save_path = os.path.join(self._save_folder, name+".jpg")
        camera.capture(save_path)
        camera.close()

        logging.info(f"[CameraModule]Saved image to {save_path}")

        return save_path


if __name__ == "__main__":
    pass

