#
#  Dexter Industries GoPiGo3 Remote Camera robot
#  With this project you can control your Raspberry Pi Robot, the GoPiGo3, with a phone, tablet, or browser.
#  Remotely view your robot as first person in your browser.
#
#  You MUST run this with python3
#  To Run:  python3 flask_server.py
#
#  Modified by Jim Harris to eliminate nipple.js and allow robot control with a standard joystick.
#  Please direct support requests to user "jimrh" at https://forum.dexterindustries.com

import os
import signal
import sys
import logging
from time import sleep

#  Use my custom version of the easygopigo3 libraries
sys.path.insert(0, '/home/pi/Project_Files/Projects/GoPiGo3/Software/Python')

from werkzeug.datastructures import ResponseCacheControl

#  check if it's ran with Python3
assert sys.version_info[0:1] == (3,)

#  imports needed for web server
from flask import Flask, jsonify, render_template, request, Response, send_from_directory, url_for
from werkzeug.serving import make_server
from gopigo3 import FirmwareVersionError
from easygopigo3 import EasyGoPiGo3

#  imports needed for stream server
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
### Basic Global Constants ###
##############################

force = float(0.00)
normal_speed = int(150)  #  Max speed if the trigger is pressed half-way
turbo_speed = int(300)  #  Max speed if the trigger is fully pressed
speed = int(0)  #  this represents the currently selected maximum, either normal or turbo speed
desired_speed = int(0)  #  This is the adjusted speed based on joystick force.
vcenter = vposition = int(92)  #  The "calibrated" positions for Charlie's head 
hcenter = hposition = int(88)  #  to be centered in both axes.

#  Set the movement step size
servo_step_size = int(5)

#  Directory Path can change depending on where you install this file.  Non-standard installations
#  may require you to change this directory.
#
#  If you install this in directory "x", both "static" and "templates"
#  should be subdirectories of directory "x".
#  Example: This file is placed in /home/pi/project. Then you should place both
#  "static" and "templates" one directory below it - /home/pi/project/templates and
#  /home/pi/project/static
#
#  TODO:  Figure out how to make this self-referencing so that the user can put this wherever he wants.
directory_path = '/home/pi/Project_Files/Projects/New_Remote_Camera_Robot/static'

##################################
### End Basic Global Constants ###
##################################

#  for triggering the shutdown procedure when a signal is detected
keyboard_trigger = Event()
def signal_handler(signal, frame):
    logging.info('Signal detected. Stopping threads.')
    my_gopigo3.stop()
    keyboard_trigger.set()

#  Create instance of the EasyGoPiGo class so that we
#  can use the GoPiGo functionality.
try:
    my_gopigo3 = EasyGoPiGo3(use_mutex = True)
except IOError:
    logging.critical('GoPiGo3 is not detected.')
    sys.exit(1)
except FirmwareVersionError:
    logging.critical('GoPiGo3 firmware needs to be updated')
    sys.exit(2)
except Exception:
    logging.critical("Unexpected error when initializing GoPiGo3 object")
    sys.exit(3)

#  Instantiate "servo" objects
servo1 = my_gopigo3.init_servo('SERVO1')
servo2 = my_gopigo3.init_servo('SERVO2')

#  Set the absolute maximum speed for the robot
#  If you try to set a speed greater than this, it won't go any faster no matter what value you send.
my_gopigo3.set_speed(turbo_speed)

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

#  Center Charlie's head
def center_head():
    global vposition
    global vcenter
    global hposition
    global hcenter

    vposition = vcenter
    hposition = hcenter
    move_head(hposition, vposition)
    return(0)

#  Shake Charlie's head - just to prove he's alive! ;)
def shake_head():
    vposition = vcenter
    hpos = hcenter

#    print("Shaking Charlie's Head From Side To Side\n")
    hposition = 110
    move_head(hposition, vposition)
    hposition = 84
    move_head(hposition, vposition)

#    print("Centering Charlie's head horizontally\n")
    center_head()

#    print("Moving Charlie's Head Up And Down\n")
    vposition = 110
    move_head(hposition, vposition)
    vposition = 66
    move_head(hposition, vposition)

#    print("Re-centering Charlie's head vertically\n")
    center_head()
    return(0)

#  Modern browsers now require CORS headers to be returned from certain
#  browser resource requests otherwise the resource is blocked.
#  Note that this may need updating in the future as I understand things better.

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
    #  get the query
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
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate" #  HTTP 1.1.
    resp.headers["Pragma"] = "no-cache" #  HTTP 1.0.
    resp.headers["Expires"] = "Wed, 21 Oct 2015 07:28:00 GMT" #  Proxies.
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
#   These routines calculate the various speed constants we'll
#   need while running the robot as a fraction/percentage of
#   speed vs force or desired_speed vs the x_axis deflection.
#
#   Desired_speed is the fraction of the currently allowable maximum speed, (either normal or turbo)
#   represented by the deflection of the joystick, either forward or backwards.
#   If the robot is moving ahead or backwards, this is the speed of both wheels
#   If the robot is turning, this is the speed of the outside wheel.

def calc_desired_speed(speed, force):
    desired_speed = int(round_up(speed * force))
    if desired_speed > speed:
        desired_speed = speed
    return (desired_speed)

#  calc_differential_speed
#  When making a turn, the "inside wheel", (the wheel being turned toward),
#  should spin more slowely than the "outside wheel" by some factor based
#  on the degree of x_axis deflection - the greater the deflection,
#  the slower the inside wheel should turn
#
#  calc_differential_speed calculates the reduced speed value to apply to the inside wheel
#  using the formula round_up(desired_speed - abs(desired_speed * x_axis))

def calc_differential_speed(desired_speed, x_axis):
    differential_speed = int(round_up(desired_speed - abs(desired_speed * x_axis)))
    if differential_speed > desired_speed:
        differential_speed = desired_speed
    return (differential_speed)

#  Implement "correct" (away from zero) rounding for both
#  positive and negative numbers
#  ref: https://www.pythontutorial.net/advanced-python/python-rounding/

def round_up(x):
    x = 100 * x  #  This will allow two decimal digits of precision ranging from zero to one.
    if x > 0:
        return (int(x + 0.5) / 100)
    elif x < 0:
        return (int(x - 0.5) / 100)
    else:
        return(0)

def process_robot_commands(args):
#    return()
    global vposition
    global hposition
    global servo_step_size
    global normal_speed
    global turbo_speed
    global speed

    controller_status = str(args['controller_status'])
    motion_state = str(args['motion_state'])
    direction = str(args['angle_dir'])
    time_stamp = int(args['time_stamp'])
    x_axis = float(args['x_axis'])
    y_axis = float(args['y_axis'])
    head_x_axis = float(args['head_x_axis'])
    head_y_axis = float(args['head_y_axis'])
    force = float(args['force'])
    trigger_1 = int(args['trigger_1'])
    trigger_2 = int(args['trigger_2'])
    head_enable = int(args['head_enable'])

#  Mask x_axis for speed testing
#    x_axis = 0

#  This reduces the x_axis sensitivity
#  Select a number that allows the x_axis to do what is necessary,
#  without undue "touchyness"
    x_axis = x_axis * 0.50  #  reduces sensitivity by a factor of 2.

#  Enable "Turbo" speed
    if trigger_2 == 1:
        speed = turbo_speed
    else:
        speed = normal_speed

    #  Insist on sane values
    if (abs(x_axis)) < 0.10: #  provide a little bit of dead-zone for the x_axis
        x_axis = 0

    if x_axis > 1:
        x_axis = 1

    elif x_axis < -1:
        x_axis = -1

    elif y_axis > 1:
        y_axis = 1

    elif y_axis < -1:
        y_axis - -1

    elif force > 1:
        force = 1

    else:
        pass


############################
##    Motion Selection    ##
############################
#
#  Depending on the position of the x and y axes
#  and the state of trigger_1, we determine
#  **IF** the robot should be moving,
#  and **WHAT DIRECTION** it should be moving in.
#
    if force == 0 or trigger_1 == 0:
        my_gopigo3.stop()
        print("Robot Stopped. . .\n")

    elif trigger_1 == 1 and y_axis < 0:
        #  We're moving forward - either straight, left, or right.
        print("The robot is moving forward and is ", end="")  #  "end=" means print the next part on the same line as this
        
        #  if we're not moving directly forward, the inside wheel must be slower
        #  than the outside wheel by some percentage.

        #  When moving to the left, the left wheel must be moving slower than
        #  the right wheel by some percentage depending on the sharpness of the turn.
        #  In order to be able to regulate the degree of sharpness of the turn with a degree of precision
        #  We need to use "set_motor_dps" because "set_motor_dps" allows the wheels to be set to individual speeds
        #  based on the calculated speeds for each wheel.

        if x_axis < 0:  #  Moving fowrard to the left
            desired_speed = int(calc_desired_speed(speed, force))
            differential_speed = int(calc_differential_speed(desired_speed, x_axis))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, desired_speed)
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, differential_speed)
            print("moving forward to the left\n")

            #  Moving to the right, we apply the same logic as before, but swap wheels.
        elif x_axis > 0:  #  Moving fowrard to the right
            desired_speed = int(calc_desired_speed(speed, force))
            differential_speed = int(calc_differential_speed(desired_speed, x_axis))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, desired_speed)
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, differential_speed)
            print("moving forward to the right\n")

        else:  #  Moving directly forward
            desired_speed = int(calc_desired_speed(speed, force))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, desired_speed)
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, desired_speed)
            print("moving forward straight ahead\n")

    elif trigger_1 == 1 and y_axis > 0:
        #
        #  We're moving backward
        #
        #  This is the exact same logic and calculation as moving forward
        #  Except that it's "backwards" (bad pun!)
        #  We do this by changing the sign of the speed requested.

        #  if we're not moving directly backward, the inside wheel must be slower
        #  than the outside wheel by some percentage.
        print("The robot is moving backward and is ", end="")

        #  reduce maximum reverse speed to 1/2 forward speed
        speed = speed * 0.5

        if x_axis < 0:  #  Moving backward to the left
            #  Moving to the left, the left wheel must be moving slower than
            #  the right wheel by some percentage.
            desired_speed = int(calc_desired_speed(speed, force))
            differential_speed = int(calc_differential_speed(desired_speed, x_axis))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, -desired_speed)
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, -differential_speed)
            print("moving backward to the left\n")

        elif x_axis > 0:  #  Moving backward to the right
            #  Moving to the right, we apply the same logic, but swap wheels.
            desired_speed = int(calc_desired_speed(speed, force))
            differential_speed = int(calc_differential_speed(desired_speed, x_axis))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, -desired_speed)
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, -differential_speed)
            print("moving backward to the right\n")

        else:  #  Moving directly backward.
            desired_speed = int(calc_desired_speed(speed, force))
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_LEFT, -desired_speed)
            my_gopigo3.set_motor_dps(my_gopigo3.MOTOR_RIGHT, -desired_speed)
            print("moving straight backward\n")


###################################
##    Head Movement Selection    ##
###################################
#
#  If we're not receiving movement messages, maybe it's a head motion request?
#
#  Use "if" instead of "elif" here because the logic falls through all thge "elif's"
#  like they were "switch-case" statements.  Here we want the arrow routines
#  to be executed independently of the robot's motion.
#
    if motion_state == 'ArrowUp':
        print('\nmoving head up\n')
        vposition += servo_step_size
        move_head(hposition, vposition)
        print(f'vposition is {vposition} - hposition is {hposition}\n')

    elif motion_state == 'ArrowDown':
        print('\nmoving head down\n')
        vposition -= servo_step_size
        move_head(hposition, vposition)
        print(f'vposition is {vposition} - hposition is {hposition}\n')

    elif motion_state == 'ArrowRight':
        print('\nmoving head right\n')
        hposition += servo_step_size
        if hposition >= 180:
            hposition = 180
        move_head(hposition, vposition)
        print(f'vposition is {vposition} - hposition is {hposition}\n')

    elif motion_state == 'ArrowLeft':
        print('\nmoving head left\n')
        hposition -= servo_step_size
        if hposition <= 0:
            hposition = 0
        move_head(hposition, vposition)
        print(f'vposition is {vposition} - hposition is {hposition}\n')

    elif motion_state == 'Home':
        print("\nCentering Head\n")
        center_head()
        servo1.disable_servo()
        servo2.disable_servo()
        print(f'vposition is {vposition} - hposition is {hposition}\n')

    elif motion_state == 'Escape':
        print("A shutdown command was recieved from the connected browser.\nSending the shutdown message to the server's event handler.\n")
        my_gopigo3.stop()
        keyboard_trigger.set()        

    else:
        motion_state = 'unknown'
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
            #  New frame, copy the existing buffer's content and notify all
            #  clients it's available
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
    #  registering both types of termination signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

#  Make sure nginx is started before starting anything else
if (os.system("sudo systemctl restart nginx")) != 0:
    logging.error("Nginx did not start properly, exiting.")
    sys.exit(1)
else:
    print("\nThe nginx proxy/secure context wrapper service has successfully started.\nNginx is now listening for HTTPS connections on port 443.\n")

#  firing up the video camera (pi camera)
    camera = picamera.PiCamera()
    output = StreamingOutput()
    camera.resolution='800x600'
    camera.framerate=30
#    camera.rotation=180
    camera.meter_mode='average'
    camera.awb_mode='auto'
    camera.start_recording(output, format='mjpeg')
    stream = StreamingServer((HOST, STREAM_PORT), StreamingHandler)
    sleep(0.25)
    print("The streaming camera process has started successfully.\n")

    #  starting the video streaming server
    streamserver = Thread(target = stream.serve_forever)
    streamserver.start()
    sleep(0.25)
    print("The streaming server has started successfully on port", STREAM_PORT, "\n")

    #  starting the web server
    webserver = WebServerThread(app, HOST, WEB_PORT)
    webserver.start()
    sleep(0.25)
    print("The flask web server has started successfully on port", WEB_PORT, "\n")

    #  Shaking Charlie's head to indicate startup
    print("Charlie is signalling that the startup propcess has successfully completed by shaking his head.\n")
    shake_head()
    sleep(0.25)  #  Give head time to get centered.
    print("Joystick_Data_Test is now ready and is listening for browser connections on ports", WEB_PORT, "amd", STREAM_PORT, "\n")

    #  and run the flask server untill a keyboard event is set
    #  or the escape key is pressed
    while not keyboard_trigger.is_set():
        sleep(0.25)

    #  until some keyboard event is detected
    print(" ==========================\n")
    print("Shutdown command event received\n")

    #  begin shutdown procedure
    webserver.shutdown()
    camera.stop_recording()
    stream.shutdown()

    #  and finalize shutting them down
    webserver.join()
    streamserver.join()
    print("All web and streaming services have successfully shut down.\n")

    print("Shutting down nginx proxy. . .\n")
    os.system("sudo systemctl stop nginx")
    sleep(0.25)  #  Give server time to detach and stop
    print("The nginx proxy/secure contxt wrapper service has successfully disconnected and shut down.\n")
    sleep(0.25)

    #  Center Charlie's Head on shutdown
    shake_head()
    sleep(0.25)  #  Give head time to get centered.
    my_gopigo3.stop()  #  Just in case. . .
    print("Charlie is signalling that shutdown has successfully completed by shaking his head.\n")
    sleep(0.25)

    print("Joystick_Data_Test has fully shut down - exiting.\n")

    sys.exit(0)
