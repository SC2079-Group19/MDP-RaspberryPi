from Modules.android import AndroidLink
from Modules.CameraModule import CameraModule

def InitializeCamera():
    cm = CameraModule()
    return cm

def InitializeAndroid():
    android_link = AndroidLink()
    android_link.connect()
    return android_link


if __name__ == "__main__":
    camera = InitializeCamera()
    android_link = InitializeAndroid()
