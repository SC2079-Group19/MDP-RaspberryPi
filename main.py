from Modules.AndroidModule import AndroidModule
from Modules.CameraModule import CameraModule
from Modules.StmModule import StmModule
from Modules.ImageRecModule import ImageRecModule

def InitializeCamera():
    cm = CameraModule()
    return cm

def InitializeAndroid():
    android_link = AndroidModule()
    android_link.connect()
    return android_link

def InitializeStm():
    stm = StmModule()
    stm.connect()
    return stm

def InitializeImageRec():
    img_rec = ImageRecModule()
    return img_rec

if __name__ == "__main__":
    camera = InitializeCamera()
    android = InitializeAndroid()
    stm = InitializeStm()
    img_rec = InitializeImageRec()
