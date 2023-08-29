import logging
import requests
import os

from config import server_url, server_port


class ImageRecModule:
    def __init__(self):
        self.url = f"{server_url}/{server_port}"
    
    def predict_image(self, img_path:str):
        if not os.path.exists(img_path):
            # Image does not exist in path
            logging.warn(f"{img_path} does not exist!")
            return None

        img = open(img_path, 'rb')
        img_name = os.path.basename(img_path)

        res = requests.post(f"{self.url}/predict", files={"file": (img_name, img)})
        img_data = res.json()
        logging.debug(f"Image {img_name} is predicted to be {img_data['image_label']}")

        return img_data


if __name__ == "__main__":
    pass
