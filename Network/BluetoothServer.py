import os
import bluetooth

ServiceUUID = '94f39d29-7d6d-437d-973b-fba39e49d4ee'

class BluetoothServer:
    def __init__(self):
        self.svr_socket = None

    def Initialize(self):
        try:
            os.system("hciconfig hci0 piscan")
            self.svr_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.svr_socket.bind(("", bluetooth.PORT_ANY))
            self.svr_socket.listen(1)

            port = self.svr_socket.getsockname()[1]
            bluetooth.advertise_service(self.svr_socket, "RPi-Grp28", service_id=ServiceUUID,
                                        service_classes=[ServiceUUID, bluetooth.SERIAL_PORT_CLASS],
                                        profiles=[bluetooth.SERIAL_PORT_PROFILE])
            
            print(f"Waiting for bluetooth connection on RFCOMM CHANNEL {port}...")
            self.client_socket, client_info = self.svr_socket.accept()
        except Exception as e:
            print(f"Error in bluetooth link connection: {e}")