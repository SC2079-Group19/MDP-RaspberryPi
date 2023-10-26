import logging
import requests
import os
import json

from config import server_url, server_port


class APIServer:
    def __init__(self):
        self.url = f"http://{server_url}:{server_port}"
    
    def server_status(self):
        res = requests.get(self.url, timeout=1)
        return res.status_code

    def predict_image(self, img_path:str, strict=False):
        if not os.path.exists(img_path):
            # Image does not exist in path
            logging.warn(f"[APIServer]{img_path} does not exist!")
            return None

        img = open(img_path, 'rb')
        img_name = os.path.basename(img_path)

        res = requests.post(
            f"{self.url}/predict", 
            files={
                "file": (img_name, img),
                "json_data": (
                    'j', 
                    json.dumps({ "strict": strict }), 
                    'application/json'
                ) 
            }, 
        )
        
        try:
            img_data = res.json()
            logging.debug(f"[APIServer]Image {img_name} is predicted to be {img_data['image_label']}")
            return img_data
        except Exception as e:
            logging.warning(f"[APIServer]Error when predicting image: {e}")
            return None


    def query_path(self, data:dict):
        res = requests.post(f"{self.url}/algo", json=data)

        if res.status_code != 200:
            logging.warning(f"[APIServer]There was an error when requesting to server. Status Code: {res.status_code}")
            return None
        
        res_data = res.json()

        if res_data['error']:
            logging.warning(f"[APIServer]Error when calculating shortest path: {res_data['error']}")
            return None
        
        logging.debug("[APIServer]Successfully queried path")
        logging.debug(f"{res_data['data']}")
        return res_data['data']


    # For task 2
    def calibrate_robot(self, img_path:str):
        if not os.path.exists(img_path):
            # Image does not exist in path
            logging.warn(f"[APIServer]{img_path} does not exist!")
            return None

        img = open(img_path, 'rb')
        img_name = os.path.basename(img_path)

        res = requests.post(f"{self.url}/calibrate", files={"file": (img_name, img)})
        try:
            command_data = res.json()
            logging.debug(f"[APIServer]Calibration Commands are: {command_data['Command']}")
            return command_data["Command"]
        except Exception as e:
            logging.warning(f"[APIServer]Error when calibrating robot: {e}")
            return None
    

    def stitch_images(self):
        res = requests.get(f"{self.url}/stitch")

        if res.status_code != 200:
            logging.warning(f"[APIServer]There was an error when requesting to server. Status Code: {res.status_code}")
            return
        
        content = res.content

        logging.info(f"[APIServer]{content}")
    

if __name__ == "__main__":
    pass
