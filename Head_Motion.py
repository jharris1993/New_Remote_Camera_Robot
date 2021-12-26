#  File Head_Motion
#
#  This file provides the global routines for creating
#  instances of the servo class and the functions needed
#  to move the robots head in whatever direction is needed
#
<<<<<<< HEAD
import signal
import sys
import logging
from time import sleep
from easygopigo3 import EasyGoPiGo3
from Global_Constants import *

global vposition
global vcenter
global hposition
global hcenter

#vcenter = vposition = 93  # tilt charlie's head up slightly
#hcenter = hposition = 93
=======
from gopigo3 import FirmwareVersionError
from easygopigo3 import EasyGoPiGo3
>>>>>>> f98e9a35934a914b70fd9dfa592f8f9f6b9be161

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

#  Add instantiate "servo" object
servo1 = gopigo3_robot.init_servo('SERVO1')
servo2 = gopigo3_robot.init_servo('SERVO2')

#  Generic "head movement" routine
def move_head(hpos, vpos):
    servo1.rotate_servo(hpos)
    servo2.rotate_servo(vpos)
    sleep(0.25)
    servo1.disable_servo()
    servo2.disable_servo()
    return(0)

# Center Charlie's head
def center_head():
    global vposition
    global vcenter
    global hposition
    global hcenter

#  We need to preserve and set vposition and hposition
#  so that other routines that use vposition and hposition
#  get the fact that we've centered Charlie's head.

    vposition = vcenter
    hposition = hcenter
#    move_head(hposition, vposition)
    move_head(hcenter, vcenter)

    return(0)

# Shake Charlie's head - just to prove he's alive! ;)
def shake_head():
#    vpos = 88
#    hpos = 97
    global vposition
    global hposition

    logging.info("Centering Charlie's head\n")
    center_head()

    logging.info("Shaking Charlie's Head From Side To Side\n")
    hposition = 110
    move_head(hposition, vposition)
    hposition = 84
    move_head(hposition, vposition)

    logging.info("Centering Charlie's head horizontally\n")
    center_head()

    logging.info("Moving Charlie's Head Up And Down\n")
    vposition = 110
    move_head(hposition, vposition)
    vposition = 66
    move_head(hposition, vposition)

    logging.info("Re-centering Charlie's head vertically\n")
    center_head()
    return(0)
