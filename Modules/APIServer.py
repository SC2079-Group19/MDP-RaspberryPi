import logging
import requests
import os

from config import server_url, server_port


class APIServer:
    def __init__(self):
        self.url = f"http://{server_url}:{server_port}"
    
    def server_status(self):
        res = requests.get(self.url, timeout=1)
        return res.status_code

    def predict_image(self, img_path:str):
        if not os.path.exists(img_path):
            # Image does not exist in path
            logging.warn(f"[APIServer]{img_path} does not exist!")
            return None

        img = open(img_path, 'rb')
        img_name = os.path.basename(img_path)

        res = requests.post(f"{self.url}/predict", files={"file": (img_name, img)})
        img_data = res.json()
        logging.debug(f"[APIServer]Image {img_name} is predicted to be {img_data['image_label']}")

        return img_data


if __name__ == "__main__":
    pass
