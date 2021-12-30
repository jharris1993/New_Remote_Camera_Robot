# Servo Test
import sys
import logging
from time import sleep
from gopigo3 import FirmwareVersionError
from easygopigo3 import EasyGoPiGo3

logging.basicConfig(level = logging.DEBUG)

vcenter=88
hcenter=97

try:
    gopigo3_robot = EasyGoPiGo3()
except IOError:
    logging.critical('GoPiGo3 is not detected.')
    sys.exit(1)
except FirmwareVersionError:
    logging.critical('GoPiGo3 firmware needs to be updated')
    sys.exit(2)
except Exception:
    logging.critical("Unexpected error when initializing GoPiGo3 object")
    sys.exit(3)

servo1 = gopigo3_robot.init_servo("SERVO1")
servo2 = gopigo3_robot.init_servo("SERVO2")

if __name__ == "__main__":

# Center Charlie's head at start
    servo1.rotate_servo(97)
    sleep(0.5)
    servo1.disable_servo()
    servo2.rotate_servo(82)
    sleep(0.5)
    servo2.disable_servo()

# Shake Charlie's Head to indicate startup
    logging.info("Shaking Charlie's Head From Side To Side\n")
    servo1.rotate_servo(110)
    sleep(0.5)
    servo1.rotate_servo(84)
    sleep(0.5)
    servo1.rotate_servo(110)
    sleep(0.5)

    logging.info("Centering Charlie's head\n")
    servo1.rotate_servo(97)
    sleep(0.5)
    servo1.disable_servo()

    # Shake Charlie's Head to indicate startup
    logging.info("Moving Charlie's Head Up And Down\n")
    servo2.rotate_servo(110)
    sleep(0.5)
    servo2.rotate_servo(60)
    sleep(0.5)
    servo2.rotate_servo(110)
    sleep(0.5)

    logging.info("Re-centering Charlie's head\n")
    servo2.rotate_servo(82)
    sleep(0.5)
    servo2.disable_servo()
