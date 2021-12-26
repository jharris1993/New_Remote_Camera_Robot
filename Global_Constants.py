#  Global Remote Camera Robbot Constants
#
#  This file, when included, should provide the basic initialization
#  Of the global constants and structures needed for the
#  Remote Camera Robot program files
#
#  The object of this file is to provide a uniform definition
#  of all the global structures used in the New Remote Camera
#  Robot project.  This way, there is one, and only one, location
#  that, when edited, automagically propigates to all affected
#  procedures
#
##############################
### Basic Global Constants ###
##############################

global vposition
global vcenter
global hposition
global hcenter

global MAX_FORCE
global MIN_SPEED
global MAX_SPEED
global force_multiplier
global drive_constant
global servo_step_size
global directory_path

MAX_FORCE = 5.0
MIN_SPEED = 0.0       # forces a minimum speed if force > 0
MAX_SPEED = 500.0
force_multiplier = 1  # allows a slower, smoother startup if > 1
drive_constant = (MAX_SPEED - MIN_SPEED) / (force_multiplier * MAX_FORCE)


# calibration constants for the servo center position which are
# determined experimentally by visual inspection of the servos
# TODO: Create a servo calibration routine that is a part of the
#       control panel and saves these settings in the gpg3_config.json file.
#       This will allow these calibraton constants to be globally
#       available to any process that wants to use them.
#
# Initially the vposition and hposition of the two servos
# is set to vcenter and hcenter respectively, then hposition and vposition
# are incremented/decremented to move the servos as commanded

vcenter = vposition = 87  # tilt charlie's head up slightly
hcenter = hposition = 97

# Set the movement step size
servo_step_size = 5

# Directory Path can change depending on where you install this file.  Non-standard installations
# may require you to change this directory.
directory_path = '/home/pi/Project_Files/Projects/New_Remote_Camera_Robot/static'

##################################
### End Basic Global Constants ###
##################################
