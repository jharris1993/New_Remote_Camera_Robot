#!/usr/bin/python3
#
# Dexter Industries GoPiGo3 Remote Camera robot
# With this project you can control your Raspberry Pi Robot, the GoPiGo3, with a phone, tablet, or browser.
# Remotely view your robot as first person in your browser.
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
    logging.info('Signal detected. Stopping threads.')
    keyboard_trigger.set()

#######################
### Web Server Stuff ##
#######################

# Directory Path can change depending on where you install this file.  Non-standard installations
# may require you to change this directory.
directory_path = '/home/pi/Dexter/GoPiGo3/Projects/RemoteCameraRobot/static'

MAX_FORCE = 5.0
MIN_SPEED = 0.0
MAX_SPEED = 500.0
drive_constant = (MAX_SPEED - MIN_SPEED) / (MAX_FORCE)

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

vcenter = vposition = 93  # tilt charlie's head up slightly
hcenter = hposition = 93

# Set the movement step size
servo_step_size = 5

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

HOST = "0.0.0.0"
WEB_PORT = 5000
app = Flask(__name__, static_url_path='')

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

    vposition = vcenter
    hposition = hcenter
    move_head(hposition, vposition)
    return(0)

# Shake Charlie's head - just to prove he's alive! ;)
def shake_head():
    vpos = 88
    hpos = 97

    logging.info("Shaking Charlie's Head From Side To Side\n")
    hpos = 110
    move_head(hpos, vpos)
    hpos = 84
    move_head(hpos, vpos)

    logging.info("Centering Charlie's head horizontally\n")
    center_head()

    logging.info("Moving Charlie's Head Up And Down\n")
    vpos = 110
    move_head(hpos, vpos)
    vpos = 66
    move_head(hpos, vpos)

    logging.info("Re-centering Charlie's head vertically\n")
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
        logging.info('Starting Flask server')
        self.srv.serve_forever()

    def shutdown(self):
        logging.info('Stopping Flask server')
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
#    determined_speed = (MIN_SPEED + force) * (MAX_SPEED - MIN_SPEED) / (2 * MAX_FORCE)
    determined_speed = force * drive_constant
    if determined_speed > MAX_SPEED:
        determined_speed = MAX_SPEED

    # add case where force = 0
    if force == 0:
        determined_speed = 0

    if state == 'move':
        # for moving backward

        if angle_degrees >= 260 and angle_degrees <= 280:
            determined_speed = determined_speed / 2
            logging.info(f'Force is "{force}"')
            logging.info(f'Determined speed is "{determined_speed}"')
            logging.info(f'Angular direction is "{angle_dir}"')
            logging.info(f'vposition is {vposition} - hposition is {hposition}\n')
            gopigo3_robot.set_speed(determined_speed)
            gopigo3_robot.backward()

        # for moving to the left or forward
        if angle_degrees > 90 and angle_degrees < 260:
            logging.info(f'Force is "{force}"')
            logging.info(f'Determined speed is "{determined_speed}"')
            logging.info(f'Angular direction is "{angle_dir}"')
            logging.info(f'vposition is {vposition} - hposition is {hposition}\n')
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_RIGHT, determined_speed)

            left_motor_percentage = abs((angle_degrees - 170) / 90)
            sign = -1 if angle_degrees >= 180 else 1

            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_LEFT, determined_speed * left_motor_percentage * sign)

        # for moving to the right (or forward)- upper half
        if angle_degrees < 90 and angle_degrees >= 0:
            logging.info(f'Force is "{force}"')
            logging.info(f'Determined speed is "{determined_speed}"')
            logging.info(f'Angular direction is "{angle_dir}"')
            logging.info(f'vposition is {vposition} - hposition is {hposition}\n')
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_LEFT, determined_speed)

            right_motor_percentage = angle_degrees / 90
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_RIGHT, determined_speed * right_motor_percentage)

        # for moving to the right (or forward)- bottom half
        if angle_degrees <= 360 and angle_degrees > 280:
            logging.info(f'Force is "{force}"')
            logging.info(f'Determined speed is "{determined_speed}"')
            logging.info(f'Angular direction is "{angle_dir}"')
            logging.info(f'vposition is {vposition} - hposition is {hposition}\n')
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_LEFT, determined_speed)

            right_motor_percentage = (angle_degrees - 280) / 80 - 1
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_RIGHT, determined_speed * right_motor_percentage)

    elif state == 'ArrowUp':
        logging.info('\nmoving up\n')
        logging.info(f'Angular direction is "{angle_dir}"')
        vposition += servo_step_size
        move_head(hposition, vposition)
        logging.info(f'vposition is {vposition} - hposition is {hposition}\n')

    elif state == 'ArrowDown':
        logging.info('\nmoving down\n')
        logging.info(f'Angular direction is "{angle_dir}"')
        vposition -= servo_step_size
        move_head(hposition, vposition)
        logging.info(f'vposition is {vposition} - hposition is {hposition}\n')

    elif state == 'ArrowRight':
        logging.info('\nmoving right\n')
        logging.info(f'Angular direction is "{angle_dir}"')
        hposition += servo_step_size
        move_head(hposition, vposition)
        logging.info(f'vposition is {vposition} - hposition is {hposition}\n')

    elif state == 'ArrowLeft':
        logging.info('\nmoving left\n')
        logging.info(f'Angular direction is "{angle_dir}"')
        hposition -= servo_step_size
        move_head(hposition, vposition)
        logging.info(f'vposition is {vposition} - hposition is {hposition}\n')

    elif state == 'Home':
        logging.info("\nCentering Charlie's Head\n")
        center_head()
        state = 'stop'
        angle_dir = 'none'
        servo1.disable_servo()
        servo2.disable_servo()
        logging.info(f'Angular direction is "{angle_dir}"')
        logging.info(f'vposition is {vposition} - hposition is {hposition}\n')

    elif state == 'unknown':
        logging.info('\nUnknown (ignored) key pressed\n')

    elif state == 'stop' or force == 0:
        gopigo3_robot.stop()
        state = 'stop'
        angle_dir = 'none'
        logging.info(f'Angular direction is "{angle_dir}"')
        logging.info(f'vposition is {vposition} - hposition is {hposition}\n')
        servo1.disable_servo()
        servo2.disable_servo()

    else:
        app.logging.warning('\nunknown state sent')

    resp = Response()
    resp.mimetype = "application/json"
    resp.status = "OK"
    resp.status_code = 200

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
    camera.framerate=30
    camera.resolution='1380x720'
    camera.framerate=30
    camera.rotation=180
    camera.meter_mode='average'
    camera.awb_mode='auto'
    camera.start_recording(output, format='mjpeg')
    logging.info("Started recording with picamera")
    STREAM_PORT = 5001
    stream = StreamingServer((HOST, STREAM_PORT), StreamingHandler)

    # starting the video streaming server
    streamserver = Thread(target = stream.serve_forever)
    streamserver.start()
    logging.info("Started stream server for picamera")

    # starting the web server
    webserver = WebServerThread(app, HOST, WEB_PORT)
    webserver.start()
    logging.info("Started Flask web server\n")

    #Shaking Charlie's head to indicate startup
    shake_head()
    logging.info("Ready to go!\n")

    # and run the flask server untill a keyboard event is set
    while not keyboard_trigger.is_set():
        sleep(0.25)

    # until some keyboard event is detected
    logging.info("Keyboard event detected\n")

    # Shake Charlie's Head to indicate shutdown
    shake_head()
    logging.info("Charlie's ready to stop now. . .\n")

    # trigger shutdown procedure
    webserver.shutdown()
    camera.stop_recording()
    stream.shutdown()

    # and finalize shutting them down
    webserver.join()
    streamserver.join()
    logging.info("Stopped all threads")

    sys.exit(0)
