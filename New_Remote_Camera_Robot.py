#
# Dexter Industries GoPiGo3 Remote Camera robot
# With this project you can control your Raspberry Pi Robot, the GoPiGo3, with a phone, tablet, or browser.
# Remotely view your robot as first person in your browser.
#
# You MUST run this with python3
# To Run:  python3 flask_server.py
#
#  Modified by Jim Harris to eliminate nipple.js and allow robot control with a standard joystick.
#  Please direct support requests to user "jimrh" at https://forum.dexterindustries.com

import os
import signal
import sys
import logging
from time import sleep

#  This grabs my modified version of EasyGoPiGo3 instead of the standard package
sys.path.insert(0, "/home/pi/Project_Files/Projects/GoPiGo3/Software/Python")

from werkzeug.datastructures import ResponseCacheControl

# check if it's ran with Python3
assert sys.version_info[0:1] == (3,)

# imports needed for web server
from flask import Flask, jsonify, render_template, request, Response, send_from_directory, url_for
from werkzeug.serving import make_server
from gopigo3 import FirmwareVersionError
from easygopigo3 import EasyGoPiGo3

# imports needed for stream server
import io
import picamera
import socketserver
from threading import Condition, Thread, Event
from http import server

logging.basicConfig(level = logging.WARNING)

#  Server Global Constants
HOST = "0.0.0.0"
WEB_PORT = 5000
STREAM_PORT = 5002  #  Changed from 5001 so that nginx can listen to the outside world on that port
app = Flask(__name__, static_url_path='')


##############################
### Basic Global Variables ###
##############################

#  The main robot_data structure to hold all the necessary information that can be passed back and forth
#  to the various functions and methods.

robot = {
    "controller_status": "Disconnected",
    "motion_state": "Waiting for Joystick",
    "direction": "None",
    "time_stamp": 0,  # a large integer that, (sometimes), becomes a float (shrug shoulders)
    "x_axis": 0.00,  #  x-axis < 0, joystick pushed left - x-axis > 0, joystick pushed right
    "y_axis": 0.00,  # y-axis < 0, joystick pushed forward - y-axis > 0 , joystick pullled back
    "head_x_axis": 0.00,  #  head x and y axes mirror the joystick x and y axes
    "head_y_axis": 0.00,  #  if the pinky-switch, (head motion enable), is pressed
    "force": 0.00,  #  force is the absolute value of the y-axis deflection
    "trigger_1": 0,   # Partial primary trigger press (motion enabled)
    "trigger_2": 0,   # Full primary trigger press enables a faster, (turbo), speed
    "head_enable": 0,  #  The "pinky switch" is used as a head-motion-enable switch. The value is captured here.
    "normal_speed": 150,  #  Max speed if the trigger is pressed half-way
    "turbo_speed": 300,  #  Max speed if the trigger is fully pressed
    "speed": 0,  # this represents the currently selected maximum, either normal or turbo speed
    "desired_speed": 0,  #  This is the adjusted speed based on joystick force.
    "differential_speed": 0,  #  This is the fractional part of the desired speed used for making turns.
    "vcenter": 95,  #  The "calibrated" positions for Charlie's head 
    "hcenter": 86,  #  to be centered in both axes.
    "vposition": 92,  #  The current angular setting for the vertical angle servo
    "hposition": 88,  #  The current angular setting for the horizontal angle servo
    "reverse_speed_offset": 0.50,
    "servo_step_size": 5
    }

# Set the movement step size
# servo_step_size = int(5)

# Directory Path can change depending on where you install this file.  Non-standard installations
# may require you to change this directory.
#
# If you install this in directory "x", both "static" and "templates"
# should be subdirectories of directory "x".
# Example: This file is placed in /home/pi/project. Then you should place both
# "static" and "templates" one directory below it - /home/pi/project/templates and
# /home/pi/project/static
#
#  TODO:  Figure out how to make this self-referencing so that the user can put this wherever he wants.

# Answer to above TODO
directory_path = os.path.realpath("static")
print("directory_path =", directory_path)
# directory_path = "/home/pi/Project_Files/Projects/New_Remote_Camera_Robot/static"

##################################
### End Basic Global Constants ###
##################################

# for triggering the shutdown procedure when a signal is detected
keyboard_trigger = Event()
def signal_handler(signal, frame):
    logging.info("Signal detected. Stopping threads.")
    my_gopigo3.stop()
    keyboard_trigger.set()

#  Create instance of the EasyGoPiGo class so that we
#  can use the GoPiGo functionality.
try:
    my_gopigo3 = EasyGoPiGo3(use_mutex = True)
except IOError:
    logging.critical("GoPiGo3 is not detected.")
    sys.exit(1)
except FirmwareVersionError:
    logging.critical("GoPiGo3 firmware needs to be updated")
    sys.exit(2)
except Exception:
    logging.critical("Unexpected error when initializing GoPiGo3 object")
    sys.exit(3)

#  Instantiate "servo" objects
servo1 = my_gopigo3.init_servo("SERVO1")
servo2 = my_gopigo3.init_servo("SERVO2")

#  Set sane eye colors - "255" is insanely bright and wastes energy.
my_gopigo3.left_eye_color = (0, 80, 80)
my_gopigo3.right_eye_color = (0, 80, 80)


#  Set the absolute maximum speed for the robot
#  If you try to set a speed greater than this, it won't go any faster no matter what value you send.
my_gopigo3.set_speed(robot["turbo_speed"])

#####################################
##  Global head movement routines  ##
#####################################

#  Generic "head movement" routine
#  This is used by all the other head movement
#  routines to move the head to a specified
#  vertical and horizontal position

def move_head(hpos, vpos):
    servo1.rotate_servo(hpos)
    servo2.rotate_servo(vpos)
    sleep(0.25)
    servo1.disable_servo()
    servo2.disable_servo()
    return(0)

# Center Charlie's head
def center_head():
    move_head(robot["hcenter"], robot["vcenter"])

    #  reset position variables to prevent unintentional head "drift" in subsequent commands.
    robot["vposition"] = robot["vcenter"]
    robot["hposition"] = robot["hcenter"]
    return(0)

# Shake Charlie's head - just to prove he's alive! ;)
def shake_head():
#    print("Shaking Charlie's Head From Side To Side\n")
    robot["hposition"] = 110
    move_head(robot["hposition"], robot["vposition"])
    robot["hposition"] = 84
    move_head(robot["hposition"], robot["vposition"])

#    print("Centering Charlie's head horizontally\n")
    center_head()

#    print("Moving Charlie's Head Up And Down\n")
    robot["vposition"] = 110
    move_head(robot["hposition"], robot["vposition"])
    robot["vposition"] = 66
    move_head(robot["hposition"], robot["vposition"])

#    print("Re-centering Charlie's head vertically\n")
    center_head()
    return(0)


###################
##  Route Paths  ##
###################

#  Modern browsers now require CORS headers to be returned from certain
#  browser resource requests otherwise the resource is blocked.
#  Note that this may need updating in the future as I understand things better.

#  Allow CORS (Cros Origin Resource Sharing) by the robot
#  in response to browser "pre-flight" ("OPTION") requests.
@app.route("/robot", methods = ["OPTIONS"])
def create_CORS_response():
    resp = Response()
    resp.headers.add("Access-Control-Allow-Origin", "*")
    resp.headers.add("Access-Control-Allow-Headers", "*")
    resp.headers.add("Access-Control-Allow-Methods", "*")
    resp.mimetype = "application/json"
    resp.status = "OK"
    resp.status_code = 200
    return(resp)

@app.route("/robot", methods = ["POST"])
def get_args():
    # get the query
    args = request.args

#  Print out the received values of the arg-list so I can verify they're correct.
#    print(args, "\n")

#  "process_robot_commands" takes the argument list and parses it to derive what
#  actual robot motions are being requested.
    process_robot_commands(args)

    #  After doing all that work, send a response.
    resp = Response()

    #  Allow CORS (Cross Origin Resource Sharing) during POST
    #  Note that this is overkill, like chmod 777.  Right now I want it to **WORK**
    #  I'll worry about working **RIGHT** later. . . .

    resp.headers.add("Access-Control-Allow-Origin", "*")

    #  Force cach clearing
    #  Note: expires = 0 usually won't work
    #  To prevent caching, set to a past date
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate" # HTTP 1.1.
    resp.headers["Pragma"] = "no-cache" # HTTP 1.0.
    resp.headers["Expires"] = "Wed, 21 Oct 2015 07:28:00 GMT" # Proxies.
    resp.mimetype = "application/json"
    resp.status = "OK"
    resp.status_code = 200
    return(resp)

@app.route("/")
def index():
    return page("index.html")

@app.route("/<string:page_name>")
def page(page_name):
    return render_template("{}".format(page_name))

@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory(directory_path, path)

#####################################
##    Speed Calculation Routines   ##
#####################################
#
# These routines calculate the various speed constants we'll
# need while running the robot as a fraction/percentage of
# speed vs force or desired_speed vs the x_axis deflection.
#
# desired_speed is the fraction of speed
# represented by the joystick force where
# force = the absolute value of the y-axis reading

#  Desired_speed is the fraction of the currently allowable maximum speed, (speed, either normal or turbo)
#  represented by the deflection of the joystick, either forward or backwards.
#  If the robot is moving ahead or backwards, this is the speed of both wheels
#  If the robot is turning, this is the speed of the outside wheel.

def calc_desired_speed(speed, force):
    desired_speed = int(round_up(speed * force))
    if desired_speed > speed:
        desired_speed = speed
    elif desired_speed < 0:
        desired_speed = 0
    return (desired_speed)

#  calculate_differential_speed
#  When making a turn, the "inside wheel", (the wheel being turned toward),
#  should spin more slowely than the "outside wheel" by some factor based
#  on the degree of x_axis deflection - the greater the deflection,
#  the slower the inside wheel should turn
#
#  calculate_differential_speed calculates the reduced speed value to apply to the inside wheel
#  using the formula round_up(desired_speed - abs(desired_speed * x_axis))

def calculate_differential_speed(desired_speed, x_axis):
    differential_speed = int(round_up(desired_speed - abs(desired_speed * x_axis)))
    if differential_speed > desired_speed:
        differential_speed = desired_speed
    elif differential_speed < 0:
        differential_speed = 0
    return (differential_speed)

# Implement "correct" (away from zero) rounding for both
# positive and negative numbers
# ref: https://www.pythontutorial.net/advanced-python/python-rounding/

def round_up(x, digits=2):

#  "x" is the value to be rounded using 4/5 rounding rules
#  always rounding away from zero
#
#  "digits" is the number of decimal digits desired after the decimal divider mark.
#  (default = 2)

    if digits < 0:
        digits = 0
    elif digits > 14:
        digits = 14

#  Since the rounding formula expects the number to be of an intger magnitude,
#  "exp" is the "orders of magnitude" to multiply by to make the number an integer

    exp = 10 ** digits

#  The number to be rounded, increased in magnitude by the "exp" multiplier
    x = exp * x

    if x > 0:
        val = (int(x + 0.5) / exp)
    elif x < 0:
        val = (int(x - 0.5) / exp)
    else:
        val = 0
        
    if digits <= 0:
        return (int(val))
    else:
        return (val)

def process_robot_commands(args):
    robot["controller_status"] = str(args["controller_status"])
    robot["motion_state"] = str(args["motion_state"])
    robot["direction"] = str(args["angle_dir"])
    robot["time_stamp"] = int(args["time_stamp"])
    robot["x_axis"] = float(args["x_axis"])
    robot["y_axis"] = float(args["y_axis"])
    robot["head_x_axis"] = float(args["head_x_axis"])
    robot["head_y_axis"] = float(args["head_y_axis"])
    robot["force"] = float(args["force"])
    robot["trigger_1"] = int(args["trigger_1"])
    robot["trigger_2"] = int(args["trigger_2"])
    robot["head_enable"] = int(args["head_enable"])

#  This reduces the x_axis sensitivity
#  Select a number that allows the x_axis to do what is necessary,
#  without undue "toouchyness"
    robot["x_axis"] = robot["x_axis"] * 0.50  #  reduces sensitivity by a pre-defined factor

#  Enable "Turbo" speed
    if robot["trigger_2"] == 1:
        robot["speed"] = robot["turbo_speed"]
    else:
        robot["speed"] = robot["normal_speed"]

    # Insist on sane values
    if (abs(robot["x_axis"])) < 0.20: # provide a little bit of dead-zone for the x_axis
        robot["x_axis"] = 0

    if robot["x_axis"] > 1:
        robot["x_axis"] = 1

    elif robot["x_axis"] < -1:
        robot["x_axis"] = -1

    elif robot["y_axis"] > 1:
        robot["y_axis"] = 1

    elif robot["y_axis"] < -1:
        robot["y_axis"] - -1

    elif robot["force"] > 1:
        robot["force"] = 1

    else:
        pass


############################
##    Motion Selection    ##
############################
#  Depending on the position of the x and y axes
#  and the state of trigger_1, we determine
#  **IF** the robot should be moving,
#  and **WHAT DIRECTION** it should be moving in.
#
    if robot["force"] == 0 or robot["trigger_1"] == 0:
        my_gopigo3.stop()
        print("Robot Stopped. . .\n")

    elif robot["trigger_1"] == 1 and robot["y_axis"] < 0:
        # We're moving forward - either straight, left, or right.
        print("The robot is ", end="")
        
        # if we're not moving directly forward, the inside wheel must be slower
        # than the outside wheel by some percentage.

        # When moving to the left, the left wheel must be moving slower than
        # the right wheel by some percentage, depending on the sharpness of the turn.
        # "set_motor_dps" allows the wheels to be set to individual speeds.
        if robot["x_axis"] < 0:  #  Moving fowrard to the left
            robot["desired_speed"] = int(calc_desired_speed(robot["speed"], robot["force"]))
            robot["differential_speed"] = int(calculate_differential_speed(robot["desired_speed"], robot["x_axis"]))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, robot["desired_speed"])
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, robot["differential_speed"])
            print("moving forward to the left\n")

            # Moving to the right, we apply the same logic as before, but swap wheels.
        elif robot["x_axis"] > 0:  #  Moving fowrard to the right
            robot["desired_speed"] = int(calc_desired_speed(robot["speed"], robot["force"]))
            robot["differential_speed"] = int(calculate_differential_speed(robot["desired_speed"], robot["x_axis"]))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, robot["desired_speed"])
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, robot["differential_speed"])
            print("moving forward to the right\n")

        else:  # Moving directly forward
            robot["desired_speed"] = int(calc_desired_speed(robot["speed"], robot["force"]))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, robot["desired_speed"])
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, robot["desired_speed"])
            print("moving forward straight ahead\n")

    elif robot["trigger_1"] == 1 and robot["y_axis"] > 0:
        # We're moving backward
        #  This is the exact same logic and calculation as moving forward
        #  Except that it's "backwards" (bad pun!)
        #  We do this by changing the sign of the speed requested.

        # if we're not moving directly backward, the inside wheel must be slower
        # than the outside wheel by some percentage.
        print("The robot is: ", end="")

        #  reduce maximum reverse speed to 1/2 forward speed
        robot["speed"] = robot["speed"] * robot["reverse_speed_offset"]

        if robot["x_axis"] < 0:  #  Moving backward to the left
            # Moving to the left, the left wheel must be moving slower than
            # the right wheel by some percentage.
            robot["desired_speed"] = int(calc_desired_speed(robot["speed"], robot["force"]))
            robot["differential_speed"] = int(calculate_differential_speed(robot["desired_speed"], robot["x_axis"]))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, -robot["desired_speed"])
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, -robot["differential_speed"])
            print("moving backward to the left\n")

        elif robot["x_axis"] > 0:  #  Moving backward to the right
            # Moving to the right, we apply the same logic, but swap wheels.
            robot["desired_speed"] = int(calc_desired_speed(robot["speed"], robot["force"]))
            robot["differential_speed"] = int(calculate_differential_speed(robot["desired_speed"], robot["x_axis"]))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, -robot["desired_speed"])
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, -robot["differential_speed"])
            print("moving backward to the right\n")

        else:  #  Moving directly backward.
            robot["desired_speed"] = int(calc_desired_speed(robot["speed"], robot["force"]))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, -robot["desired_speed"])
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, -robot["desired_speed"])
            print("moving straight backward\n")

#  If we're not receiving movement messages, maybe it's a head motion request?
    if robot["motion_state"] == "ArrowUp":
        print("\nmoving head up\n")
        robot["vposition"] += robot["servo_step_size"]
        move_head(robot["hposition"], robot["vposition"])
#        print(f"robot["vposition"] is {robot["vposition"]} - robot["hposition"] is {robot["hposition"]}\n")

    elif robot["motion_state"] == "ArrowDown":
        print("\nmoving head down\n")
        robot["vposition"] -= robot["servo_step_size"]
        move_head(robot["hposition"], robot["vposition"])
#        print(f"robot["vposition"] is {robot["vposition"]} - robot["hposition"] is {robot["hposition"]}\n")

    elif robot["motion_state"] == "ArrowRight":
        print("\nmoving head right\n")
        robot["hposition"] += robot["servo_step_size"]
        if robot["hposition"] >= 180:
            robot["hposition"] = 180
        move_head(robot["hposition"], robot["vposition"])
#        print(f"robot["vposition"] is {robot["vposition"]} - robot["hposition"] is {robot["hposition"]}\n")

    elif robot["motion_state"] == "ArrowLeft":
        print("\nmoving head left\n")
        robot["hposition"] -= robot["servo_step_size"]
        if robot["hposition"] <= 0:
            robot["hposition"] = 0
        move_head(robot["hposition"], robot["vposition"])
#        print(f"robot["vposition"] is {robot["vposition"]} - robot["hposition"] is {robot["hposition"]}\n")

    elif robot["motion_state"] == "Home":
        print("\nCentering Head\n")
        center_head()
        servo1.disable_servo()
        servo2.disable_servo()
#        print(f"robot["vposition"] is {robot["vposition"]} - robot["hposition"] is {robot["hposition"]}\n")

    elif robot["motion_state"] == "Escape":
        print("A \"shutdown\" command was recieved from the browser.\n")
        print("Now requesting the server to start shutting down.\n")
        my_gopigo3.stop()
        keyboard_trigger.set()        

    else:
        robot["motion_state"] = "unknown"
#        print("\nUnknown (ignored) key pressed\n")
    return


#############################
###   Web Server Stuff    ###
############################

class WebServerThread(Thread):
    '''
    Class to make the launch of the flask server non-blocking.
    Also adds shutdown functionality to it.
    '''
    def __init__(self, app, host, port):
        Thread.__init__(self)
        self.srv = make_server(host, port, app)
#        self.srv = make_server(host, port, app, ssl_context=("/usr/local/share/ca-certificates/extra/combined.crt", "/usr/local/share/ca-certificates/extra/www.gopigo3.com.key"))
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        logging.info("Starting Flask server")
        self.srv.serve_forever()

    def shutdown(self):
        logging.info("Stopping Flask server")
        self.srv.shutdown()

#############################
### Video Streaming Stuff ###
#############################

class StreamingOutput(object):
    '''
    Class to which the video output is written to.
    The buffer of this class is then read by StreamingHandler continuously.
    '''
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b"\xff\xd8"):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    '''
    Implementing GET request for the video stream.
    '''
    def do_GET(self):
        if self.path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Age", 0)
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b"--FRAME\r\n")
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
            except Exception as e:
                logging.warning(
                    "Removed streaming client %s: %s",
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

#############################
### Aggregating all calls ###
#############################

if __name__ == "__main__":
    # registering both types of termination signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

print("\nNew Remote Camera Robot is starting with the following default values:")
print("Robot Maximum Speed = ", robot["turbo_speed"],"rotational degrees/second.")
print("Robot Normal Speed = ", robot["normal_speed"],"rotational degrees/second.")
print("Robot Reverse Speeds are set to", robot["reverse_speed_offset"], "times the forward speeds.\n")
#  Make sure nginx is started before starting anything else
if (os.system("sudo systemctl restart nginx")) != 0:
    logging.error("Nginx did not start properly, exiting.")
    sys.exit(1)
else:
    print("The nginx proxy/secure context wrapper service has successfully started")
    print("and is listening for HTTPS connections on port 443.\n")

# firing up the video camera (pi camera)
    camera = picamera.PiCamera()
    output = StreamingOutput()
    camera.resolution="800x600"
    camera.framerate=30
#    camera.rotation=180
    camera.meter_mode="average"
    camera.awb_mode="auto"
    camera.start_recording(output, format="mjpeg")
    stream = StreamingServer((HOST, STREAM_PORT), StreamingHandler)
    sleep(0.25)
    print("The streaming camera process has started successfully\n")

    # starting the video streaming server
    streamserver = Thread(target = stream.serve_forever)
    streamserver.start()
    sleep(0.25)
    print("The streaming server has started successfully on port ", STREAM_PORT)

    # starting the web server
    webserver = WebServerThread(app, HOST, WEB_PORT)
    webserver.start()
    sleep(0.25)
    print("The flask web server has started successfully on port ", WEB_PORT, "\n")

    # Shaking Charlie's head to indicate startup
    print("Charlie is signalling that the startup command has successfully run by shaking his head.\n")
    shake_head()
    sleep(0.25)  #  Give head time to get centered.
    print("Joystick_Data_Test is now listening for browser connections.\n")

    # and run the flask server untill a keyboard event is set
    # or the escape key is pressed
    while not keyboard_trigger.is_set():
        sleep(0.25)

    # until some keyboard event is detected
    print("\n ==========================\n\n")
    print("A \"shutdown\" command event was received!\n")

    # begin shutdown procedure
    webserver.shutdown()
    camera.stop_recording()
    stream.shutdown()

    # and finalize shutting them down
    webserver.join()
    streamserver.join()
    print("All web and streaming services have successfully shut down.\n")

    print("Shutting down nginx proxy. . .\n")
    os.system("sudo systemctl stop nginx")
    sleep(0.25)  #  Give server time to detach and stop
    print("The nginx proxy/secure contxt wrapper service has successfully disconnected and shut down.\n")
    sleep(0.25)

    # Center Charlie's Head on shutdown
    shake_head()
    sleep(0.25)  #  Give head time to get centered.
    my_gopigo3.stop()  # Just in case. . .
    print("Charlie is signalling that shutdown has successfully completed by shaking his head.\n")
    sleep(0.25)

    print("New Remote Camera Robot has fully shut down - exiting.\n")

    sys.exit(0)
