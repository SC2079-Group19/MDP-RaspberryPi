# Android Configs
uuid = "94f39d29-7d6d-437d-973b-fba39e49d4ee"
service_name = "MDP-Group19-RPi"

# Camera Configs
resolution = (1024, 768)
warmup_time = 0.5

# STM Configs
serial_port = "/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0002-if00-port0"
baud_rate = 115200
stm_message_len = 5
stm_command_prefixes = ("FS", "BS", "FW", "BW", "FL", "FR", "BL",
                        "BR", "TL", "TR", "A", "C", "DT", "STOP", "ZZ", 
                        "RS", "BA", "BC", "FA", "FC", "TA", "TB")

# Image Recognition Configs
server_url = "192.168.19.17" # to be changed
server_port = "5000"
