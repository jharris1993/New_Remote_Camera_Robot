#!/usr/bin/python3
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

import signal
import sys
import logging
from time import sleep

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

HOST = "0.0.0.0"
WEB_PORT = 5000
app = Flask(__name__, static_url_path='')

##############################
### Basic Global Constants ###
##############################

# calibration constants for the servo center position which are
# determined experimentally by visual inspection of the servos
#
# Initially the vposition and hposition of the two servos
# is set to vcenter and hcenter respectively, then hposition and vposition
# are incremented/decremented to move the servos as commanded

force = float(0.00)
max_speed = float(300.00)
actual_speed = (max_speed * force)
vcenter = vposition = int(87)  # tilt charlie's head up slightly
hcenter = hposition = int(97)

# Set the movement step size
servo_step_size = int(5)

# Directory Path can change depending on where you install this file.  Non-standard installations
# may require you to change this directory.
#
# If you install this in directory "x", both "static" and "templates"
# should be subdirectories of directory "x".
# Example: This file is placed in /home/pi/project. Then you should place both
# "static" and "templates" one directory below it - /home/pi/project/templates and
# /home/pi/project/static
directory_path = '/home/pi/Project_Files/Projects/New_Remote_Camera_Robot/static'

##################################
### End Basic Global Constants ###
##################################

# for triggering the shutdown procedure when a signal is detected
keyboard_trigger = Event()
def signal_handler(signal, frame):
    logging.info('Signal detected. Stopping threads.')
    gopigo3_robot.stop()
    keyboard_trigger.set()

#  Create instance of the EasyGoPiGo class so that we
#  can use the GoPiGo functionality.
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

    #  Instantiate "servo" object
servo1 = gopigo3_robot.init_servo('SERVO1')
servo2 = gopigo3_robot.init_servo('SERVO2')

#####################################
##    Speed Calculation Routines   ##
#####################################
#
# These routines calculate the various speed constants we'll
# need while running the robot as a fraction/percentage of
# max_speed vs force
#
# actual_speed is the fraction of max_speed
# represented by the joystick force where
# force = the absolute value of the y-axis reading
def calc_actual_speed(max_speed, force):
    actual_speed = max_speed * force
    print("calc_actual_speed: max_speed =", max_speed, "force =", force, "actual_speed =", actual_speed)
    return (actual_speed)

# percent_max_speed represents actual_speed as a percentage of max_speed
# for example: if max_speed is 500 and force = 0.5,
# actual_speed is 250, (max_speed * force) and
# percent_max_speed = 50 (percent of max_speed)
def calc_percent_speed(y_axis, x_axis):
#    actual_speed = calc_actual_speed(max_speed, force)
    percent_speed = (((y_axis / x_axis) / 2 ) * 100.00)
    print("calc_percent_speed: y_axis =", y_axis, "x_axis =", x_axis, "percent_speed =", percent_speed)
    return (percent_speed)
#    return()


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
    global vposition
    global vcenter
    global hposition
    global hcenter

    vposition = vcenter
    hposition = hcenter
    move_head(hposition, vposition)
    return(0)

# Shake Charlie's head - just to prove he's alive! ;)
def shake_head():
    vposition = vcenter
    hpos = hcenter

    print("Shaking Charlie's Head From Side To Side\n")
    hposition = 110
    move_head(hposition, vposition)
    hposition = 84
    move_head(hposition, vposition)

    print("Centering Charlie's head horizontally\n")
    center_head()

    print("Moving Charlie's Head Up And Down\n")
    vposition = 110
    move_head(hposition, vposition)
    vposition = 66
    move_head(hposition, vposition)

    print("Re-centering Charlie's head vertically\n")
    center_head()
    return(0)

#  Modern browsers now require CORS headers to be returned from certain
#  browser resource requests otherwise the resource is blocked.

#  Allow CORS (Cros Origin Resource Sharing) by the robot
#  in response to browser "pre-flight" ("OPTION") requests.
@app.route("/robot", methods = ["OPTIONS"])
def create_CORS_response():
    resp = Response()
    resp.headers.add("Access-Control-Allow-Origin", "*")
    resp.headers.add('Access-Control-Allow-Headers', "*")
    resp.headers.add('Access-Control-Allow-Methods', "*")
    resp.mimetype = "application/json"
    resp.status = "OK"
    resp.status_code = 200
    return(resp)

@app.route("/robot", methods = ["POST"])
def get_args():
    # get the query
    args = request.args
    print(args, "\n")
    process_robot_commands(args)
    #  After doing all that work, send a response.
    resp = Response()
    #  Allow CORS (Cross Origin Resource Sharing) during POST
    resp.headers.add("Access-Control-Allow-Origin", "*")

    #  Force cach clearing
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate" # HTTP 1.1.
    resp.headers["Pragma"] = "no-cache" # HTTP 1.0.
    resp.headers["Expires"] = "0" # Proxies.
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
    # resp = Response(send_from_directory(directory_path, path))
    # resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate" # HTTP 1.1.
    # resp.headers["Pragma"] = "no-cache" # HTTP 1.0.
    # resp.headers["Expires"] = "0" # Proxies.
    # return(resp)
    return send_from_directory(directory_path, path)

def process_robot_commands(args):
#    return()
    global vposition
    global hposition
    global servo_step_size

    controller_status = str(args['controller_status'])
    motion_state = str(args['motion_state'])
    direction = str(args['angle_dir'])
    time_stamp = float(args['time_stamp'])
    x_axis = float(args['x_axis'])
    y_axis = float(args['y_axis'])
    head_x_axis = float(args['head_x_axis'])
    head_y_axis = float(args['head_y_axis'])
    force = float(args['force'])
    trigger_1 = int(args['trigger_1'])
    trigger_2 = int(args['trigger_2'])
    head_enable = int(args['head_enable'])

############################
##    Motion Selection    ##
############################
#  Depending on the position of the x and y axes
#  and the state of trigger_1, we determine
#  **IF** the robot should be moving,
#  and **WHAT DIRECTION** it should be moving in.
#
    if force == 0 or trigger_1 == 0:
        gopigo3_robot.stop()
        print("Robot Stopped. . .\n")

    elif trigger_1 == 1 and y_axis < 0:
        # We're moving forward - either straight, left, or right.
        print("The robot is moving forward and is ")
        
        # if we're not moving directly forward, the inside wheel must be slower
        # than the outside wheel by some percentage.

        # When moving to the left, the left wheel must be moving slower than
        # the right wheel by some percentage, depending on the sharpness of the turn.
        # "set_motor_dps" allows the wheels to be set to individual speeds.
        if x_axis < 0:  #  Moving fowrard to the left
            actual_speed = int(calc_actual_speed(max_speed, force))
            percent_speed = int(calc_percent_speed(y_axis, x_axis))
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_RIGHT, actual_speed)
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_LEFT, percent_speed)
            print("moving forward to the left\n")

            # Moving to the right, we apply the same logic as before, but swap wheels.
        elif x_axis > 0:  #  Moving fowrard to the right
            actual_speed = int(calc_actual_speed(max_speed, force))
            percent_speed = int(calc_percent_speed(y_axis, x_axis))
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_LEFT, actual_speed)
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_RIGHT, -percent_speed)
            print("moving forward to the right\n")

        else:  # Moving directly forward
            actual_speed = int(calc_actual_speed(max_speed, force))
            gopigo3_robot.set_speed(actual_speed)
            gopigo3_robot.forward()
            print("moving forward straight ahead\n")

    elif trigger_1 == 1 and y_axis > 0:
        # We're moving backward
        # if we're not moving directly backward, the inside wheel must be slower
        # than the outside wheel by some percentage.
        print("The robot is moving backward and is ")

        if x_axis < 0:  #  Moving backward to the left
            # Moving to the left, the left wheel must be moving slower than
            # the right wheel by some percentage.
            actual_speed = int(calc_actual_speed(max_speed, force))
            percent_speed = int(calc_percent_speed(y_axis, x_axis))
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_RIGHT, -actual_speed)
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_LEFT, percent_speed)
            print("moving backward to the left\n")

        elif x_axis > 0:  #  Moving backward to the right
            # Moving to the right, we apply the same logic, but swap wheels.
            actual_speed = int(calc_actual_speed(max_speed, force))
            percent_speed = int(calc_percent_speed(y_axis, x_axis))
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_LEFT, -actual_speed)
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_RIGHT, -percent_speed)
            print("moving backward to the right\n")

        else:  #  Moving directly backward.
            actual_speed = int(calc_actual_speed(max_speed, force))
            gopigo3_robot.set_speed(actual_speed)
            gopigo3_robot.backward()
            print("moving straignt backward\n")

    if motion_state == 'ArrowUp':
        print('\nmoving head up\n')
#        print(f'Angular direction is "{direction}"')
        vposition += servo_step_size
        move_head(hposition, vposition)
        print(f'vposition is {vposition} - hposition is {hposition}\n')

    elif motion_state == 'ArrowDown':
        print('\nmoving head down\n')
#        print(f'Angular direction is "{direction}"')
        vposition -= servo_step_size
        move_head(hposition, vposition)
        print(f'vposition is {vposition} - hposition is {hposition}\n')

    elif motion_state == 'ArrowRight':
        print('\nmoving head right\n')
#        print(f'Angular direction is "{direction}"')
        hposition += servo_step_size
        if hposition >= 180:
            hposition = 180
        move_head(hposition, vposition)
        print(f'vposition is {vposition} - hposition is {hposition}\n')

    elif motion_state == 'ArrowLeft':
        print('\nmoving head left\n')
#        print(f'Angular direction is "{direction}"')
        hposition -= servo_step_size
        if hposition <= 0:
            hposition = 0
        move_head(hposition, vposition)
        print(f'vposition is {vposition} - hposition is {hposition}\n')

    elif motion_state == 'Home':
        print("\nCentering Head\n")
        center_head()
#        motion_state = 'Stopped'
#        direction = 'Centered Head'
        servo1.disable_servo()
        servo2.disable_servo()
#        print(f'Angular direction is "{direction}"')
        print(f'vposition is {vposition} - hposition is {hposition}\n')

    elif motion_state == 'Escape':
        print("Shutdown command recieved from the robot.\n")
        gopigo3_robot.stop()
        keyboard_trigger.set()        

    else:
        motion_state = 'unknown'
#        print('\nUnknown (ignored) key pressed\n')
    return()


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
#        self.srv = make_server(host, port, app, ssl_context=('/usr/local/share/ca-certificates/extra/combined.crt', '/usr/local/share/ca-certificates/extra/www.gopigo3.com.key'))
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        logging.info('Starting Flask server')
        self.srv.serve_forever()

    def shutdown(self):
        logging.info('Stopping Flask server')
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
        if buf.startswith(b'\xff\xd8'):
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
        if self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
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
    # registering both types of signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # firing up the video camera (pi camera)
#    camera = picamera.PiCamera(resolution='320x240', framerate=30)
    camera = picamera.PiCamera()
    output = StreamingOutput()
    camera.resolution='800x600'
    camera.framerate=30
#    camera.rotation=180
    camera.meter_mode='average'
    camera.awb_mode='auto'
    camera.start_recording(output, format='mjpeg')
    print("Started recording with picamera")
    STREAM_PORT = 5002
    stream = StreamingServer((HOST, STREAM_PORT), StreamingHandler)

    # starting the video streaming server
    streamserver = Thread(target = stream.serve_forever)
    streamserver.start()
    print("Started stream server for picamera")

    # starting the web server
    webserver = WebServerThread(app, HOST, WEB_PORT)
    webserver.start()
    print("Started Flask web server\n")

    #Shaking Charlie's head to indicate startup
    shake_head()
    print("Joystick_Data_Test is now listening for browser connections.\n")

    # and run the flask server untill a keyboard event is set
    # or the escape key is pressed
    while not keyboard_trigger.is_set():
        sleep(0.25)

    # until some keyboard event is detected
    print("Shutdown command event received\n")

    # Center Charlie's Head on shutdown
    shake_head()
    sleep(0.25)  #  Give head time to get centered.
    gopigo3_robot.stop()  # Just in case. . .
    print("Charlie is now ready to stop. . .\n")

    # begin shutdown procedure
    webserver.shutdown()
    camera.stop_recording()
    stream.shutdown()

    # and finalize shutting them down
    webserver.join()
    streamserver.join()
    logging.info("Stopped all threads")
    print("Joystick_Data_Test has fully shut down - exiting.")

    sys.exit(0)
