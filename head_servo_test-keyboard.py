#  Head Servo test - keyboard
#  This routine tests receiving direction information
#  from the keyboard and applying it to the head servos.
#
#  It uses the pseudo-joystick library "nipple.js"
#  provided by yoannmoinet.  License info and a link to his
#  GitHub repo can be found at https://yoannmoi.net/nipplejs.
#
#  This is an adaptation of the "remote_robot.py" file included with
#  Dexter Industries' Raspbian for Robots.
#
#  Unless otherwise specified, this file and it's associated support
#  files are licensed under the Free Software Foundation, Inc.'s GPL-3
#  copyright license.  Copies of this license can be obtained from the
#  Free Software Foundation, Inc. web site locate at
#  https://www.gnu.org/licenses/gpl-3.0.html.
#
#  In this routine, both keyboard event listeners within
#  the html file, and the motion routines within nipple.js
#  are used to control the robot.
#
#  *  The keyboard is used to move the head PAN-and-TILT servos
#     up, down, left, or right as desired.  The "home" key centers
#     both servos.
#     Combination movements, (both up and left, for example), are NOT supported
#     and may produce unpredictable results.
#
#  *  The mouse is used to physically move the robot by clicking and
#     dragging the mouse in the direction you want the robot to move.
#     Combination movements, (both up and left, for example), ARE supported
#     for mouse controlled motion input.
#
#  *  Keyboard events: (key pressed)
#     Keys held down begin to repeat.
#     *  Up arrow:  Moves the head TILT servo up.
#     *  Down arrow:  Moves the head TILT servo down.
#     *  Left arrow:  Moves the head PAN servo left.
#     *  Right arrow:  Moves the head PAN servo right.
#     *  "Home" key:  Centers both the TILT and PAN servos
#
#  *  Mouse events:
#     *  Mouse "left button-pressed":  Changes state from "stopped" to "moving".
#     *  Mouse "drag" upward:  Moves the robot forward.
#     *  Mouse "drag" downward:  Moves the robot backward.
#     *  Mouse "drag" left:  Moves the robot left.
#     *  Mouse "drag" right:  Moves the robot right.
#     *  Mouse "left button-released":  Changes state from "moving" to "stopped".
#
# You MUST run this with python3
# To Run:  python3 flask_server.py

import signal
import sys
import logging
from time import sleep

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

logging.basicConfig(level = logging.DEBUG)

# for triggering the shutdown procedure when a signal is detected
keyboard_trigger = Event()
def signal_handler(signal, frame):
    logging.info('\nSignal detected. Stopping threads.\n')
    keyboard_trigger.set()

#######################
### Web Server Stuff ##
#######################

# Directory Path can change depending on where you install this file.  Non-standard installations
# may require you to change this directory.
directory_path = '/home/pi/Dexter/GoPiGo3/Projects/RemoteCameraRobot/static'

MAX_FORCE = 5.0
MIN_SPEED = 100
MAX_SPEED = 500

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

vcenter = vposition = 100
hcenter = hposition = 93

# Set the movement step size

servo_step_size = 5

#  Start an instance of the GoPiGo robot class via
#  EasyGoPiGo3

try:
    gopigo3_robot = EasyGoPiGo3()
except IOError:
    logging.critical('\nGoPiGo3 is not detected.\n')
    sys.exit(1)
except FirmwareVersionError:
    logging.critical('\nGoPiGo3 firmware needs to be updated\n')
    sys.exit(2)
except Exception:
    logging.critical('\nUnexpected error when initializing GoPiGo3 object\n')
    sys.exit(3)

HOST = '0.0.0.0'
WEB_PORT = 5000
app = Flask(__name__, static_url_path='')

#  Add instantiate "servo" object
servo1 = gopigo3_robot.init_servo('SERVO1')
servo2 = gopigo3_robot.init_servo('SERVO2')

#  Generic "head movement" routine
def move_head(hpos, vpos):
    servo1.rotate_servo(hpos)
#    sleep(0.50)
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
    vpos = 88
    hpos = 97

    print("Shaking Charlie's Head From Side To Side\n")
    hpos = 110
    move_head(hpos, vpos)
    hposition = 84
    move_head(hpos, vpos)

    print("Centering Charlie's head horizontally\n")
    center_head()

    print("Moving Charlie's Head Up And Down\n")
    vposition = 110
    move_head(hpos, vpos)
    vposition = 66
    move_head(hpos, vpos)

    print("Re-centering Charlie's head vertically\n")
    center_head()
    return(0)

class WebServerThread(Thread):
    '''
    Class to make the launch of the flask server non-blocking.
    Also adds shutdown functionality to it.
    '''
    def __init__(self, app, host, port):
        Thread.__init__(self)
        self.srv = make_server(host, port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        print('\nStarting Flask server\n')
        self.srv.serve_forever()

    def shutdown(self):
        print('\nStopping Flask server\n')
        self.srv.shutdown()

@app.route("/robot", methods = ["POST"])
def robot_commands():
    global vposition
    global hposition
    global servo_step_size

    # get the query
    args = request.args
    state = args['state']
    angle_degrees = int(float(args['angle_degrees']))
    angle_dir = args['angle_dir']
    force = float(args['force'])

    if state == 'move':
        if angle_dir == 'up':
            print('\nmoving up\n')
            print(angle_dir)
            vposition += servo_step_size
            servo2.rotate_servo(vposition)
            sleep(0.25)
            print(vposition)

        if angle_dir == 'down':
            print('\nmoving down\n')
            print(angle_dir)
            vposition -= servo_step_size
            servo2.rotate_servo(vposition)
            sleep(0.25)
            print(vposition)

        if angle_dir == 'left':
            print('\nmoving left\n')
            print(angle_dir)
            hposition -= servo_step_size
            servo1.rotate_servo(hposition)
            sleep(0.25)
            print(hposition)

        if angle_dir == 'right':
            print('\nmoving right\n')
            print(angle_dir)
            hposition += servo_step_size
            sleep(0.25)
            servo1.rotate_servo(hposition)
            print(hposition)

    elif state == 'ArrowUp':
        print('\nmoving up\n')
        print(angle_dir)
        vposition += servo_step_size
        move_head(hposition, vposition)
        print(f'\nvposition is {vposition} - hposition is {hposition}\n')

    elif state == 'ArrowDown':
        print('\nmoving down\n')
        print(angle_dir)
        vposition -= servo_step_size
        move_head(hposition, vposition)
        print(f'\nvposition is {vposition} - hposition is {hposition}\n')

    elif state == 'ArrowRight':
        print('\nmoving right\n')
        print(angle_dir)
        hposition += servo_step_size
        move_head(hposition, vposition)
        print(f'\nvposition is {vposition} - hposition is {hposition}\n')

    elif state == 'ArrowLeft':
        print('\nmoving left\n')
        print(angle_dir)
        hposition -= servo_step_size
        move_head(hposition, vposition)
        print(f'\nvposition is {vposition} - hposition is {hposition}\n')

    elif state == 'Home':
        print("\nCentering Charlie's Head\n")
        center_head()
        state = 'stop'
        angle_dir = 'none'
        servo1.disable_servo()
        servo2.disable_servo()
        print(f'\nvposition is {vposition} - hposition is {hposition}\n')

    elif state == 'stop' or force == 0:
        state = 'stop'
        angle_dir = 'none'
        servo1.disable_servo()
        servo2.disable_servo()

    elif state == 'unknnown':
        print('\nUnknown (ignored) key pressed\n')

    else:
        logging.warning('\nunknown state sent')

    resp = Response()
    resp.mimetype = "application/json"
    resp.status = "OK"
    resp.status_code = 200

    print('Battery Voltage is', round(gopigo3_robot.volt(), 2), '\n')
    return resp

@app.route("/")
def index():
    return page("index.html")

@app.route("/<string:page_name>")
def page(page_name):
    return render_template("{}".format(page_name))

@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory(directory_path, path)

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
                    'Removed streaming client %s: %s\n',
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
    # Capture ctl-D to re-center Charlie's head
    signal.signal(signal.SIGQUIT, center_head)

    # firing up the video camera (pi camera)
#    camera = picamera.PiCamera(resolution='320x240', framerate=30)
    camera = picamera.PiCamera()
    output = StreamingOutput()
    camera.resolution='1380x720'
    camera.framerate=30
    camera.rotation=180
    camera.start_recording(output, format='mjpeg')
    print('\nStarted recording with picamera\n')
    STREAM_PORT = 5001
    stream = StreamingServer((HOST, STREAM_PORT), StreamingHandler)

    # starting the video streaming server
    streamserver = Thread(target = stream.serve_forever)
    streamserver.start()
    print('\nStarted stream server for picamera\n')

    # starting the web server
    webserver = WebServerThread(app, HOST, WEB_PORT)
    webserver.start()
    print('\nStarted Flask web server\n')

    #Shaking Charlie's head to indicate startup
    shake_head()
    print('Battery Voltage is', round(gopigo3_robot.volt(), 2), '\n')
    print("Ready to go!\n")

    # and run it until a keyboard event is set
    while not keyboard_trigger.is_set():
        sleep(0.25)

    # until some keyboard event is detected
    print('\nKeyboard ABORT detected\n')

    # Shake Charlie's Head to indicate shutdown
    shake_head()
    print('Battery Voltage is', round(gopigo3_robot.volt(), 2), '\n')
    print("Charlie is ready to stop now. . .\n")

    # trigger shutdown procedure
    webserver.shutdown()
    camera.stop_recording()
    stream.shutdown()

    # and finalize shutting them down
    webserver.join()
    streamserver.join()
    print('\nStopped all threads')

    sys.exit(0)
