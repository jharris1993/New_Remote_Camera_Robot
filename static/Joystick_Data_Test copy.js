//
//  Joystick Data Test
//  This should return data to index.html
//

var server_address = window.location.protocol + "//" + window.location.host + "/robot";
var joystick_data;
var js = '';

//  Formal definition of "gopigo3_joystick"
var gopigo3_joystick = {
  controller_status: 'Disconnected',
  motion_state: 'Waiting for Joystick',
  angle_dir: 'None',
  time_stamp: 0,  // a large integer that occasioally shows up as a float (shrugs shoulders)
  x_axis: 0.00,  // x-axis < 0 = pusshed left, > 0 = pushed right
  y_axis: 0.00,  // y-axis < 0 = pushed forward, > 0 = pulled backward
  head_x_axis: 0.00,  //  These are the same as x-axis and y-axis if the "head_enable"
  head_y_axis: 0.00,  //  button is pressed.
  force: 0.00,  // force is the absolute value of the y-axis value
  trigger_1: 0,   // Partial primary trigger press (slow speed)
  trigger_2: 0,   // Full primary trigger press  (faster speed - not implemented yet)
  head_enable: 0  // Pinky-switch press  (enable joystick to move head)
};

window.addEventListener("gamepadconnected", (event) => {
  js = event.gamepad;
  gamepad_connected();  // Gamepad is now connected
  send_data(gopigo3_joystick)  // send it to the robot
//        get_more_data();  // continue service loop
});

window.addEventListener("gamepaddisconnected", (event) => {
  gopigo3_joystick.controller_status = "Disconnected"; // Joystick disconnected, so set state to "diusconnected"
  gopigo3_joystick.motion_state = 'Waiting for Joystick';
  gamepad_disconnected(); // clear out stale data
  send_data(gopigo3_joystick)  // send it to the robot
//        get_more_data(); // continue service loop
});

  //  Add section for keyboard listener
window.addEventListener('keydown', (event) => {
    keyName = event.key;
    gopigo3_joystick.motion_state = keyName;
    send_data(gopigo3_joystick)  // send it to the robot
//          get_more_data(); // continue service loop
});

function  get_gamepad_data() {
  js = (navigator.getGamepads && navigator.getGamepads()) || (navigator.webkitGetGamepads && navigator.webkitGetGamepads());

  collate_data(js[0]);  //  Collect variable data to be sent

  what_i_am_doing(gopigo3_joystick)  // Collect motion status

  send_data(gopigo3_joystick);  // Send normalized data to 'bot

  // Update the on-screen data with the nrmalized data
  setOnScreen(gopigo3_joystick);
  // Here we loop on the requestAnimationFrame after a timeout (in ms)
  // to prevent saturating the network every 1/60th second (or faster)
  // depending on the capabilities of the monitor/browser being used.
  // setTimeout(get_more_data, 250);
  requestAnimationFrame(is_something_happening(jsdata, gopigo3_joystick));
  return;
}

// gamepad_connected is called during the event handling when a joystick
// is connected, and initializes the gamepad data to a sane "connected" value
function gamepad_connected() {
  gopigo3_joystick.controller_status = 'Connected'; // Joystick connected but not moving
  gopigo3_joystick.motion_state = 'Stopped';
  gopigo3_joystick.angle_dir = 'None';
  gopigo3_joystick.time_stamp = 0;
  gopigo3_joystick.x_axis = 0.00;
  gopigo3_joystick.y_axis = 0.00;
  gopigo3_joystick.head_x_axis = 0.00;
  gopigo3_joystick.head_y_axis = 0.00;
  gopigo3_joystick.force = 0.00;
  gopigo3_joystick.trigger_1 = 0;
  gopigo3_joystick.trigger_2 = 0;
  gopigo3_joystick.head_enable = 0;
  send_data(gopigo3_joystick)  // send it to the robot
//        get_more_data(); // continue service loop
  return;
}

function gamepad_disconnected() {
  gopigo3_joystick.controller_status = 'Disconnected';
  gopigo3_joystick.motion_state = 'Waiting for Joystick';
  gopigo3_joystick.angle_dir = 'None';
  gopigo3_joystick.time_stamp = 0;
  gopigo3_joystick.x_axis = 0.00;
  gopigo3_joystick.y_axis = 0.00;
  gopigo3_joystick.head_x_axis = 0.00;
  gopigo3_joystick.head_y_axis = 0.00;
  gopigo3_joystick.force = 0.00;
  gopigo3_joystick.trigger_1 = 0;
  gopigo3_joystick.trigger_2 = 0;
  gopigo3_joystick.head_enable = 0;
  send_data(gopigo3_joystick)  // send it to the robot
//        get_more_data(); // continue service loop
  return;
};

//  Collate data collects all the data, normalizes it, packages it, and prepares
//  for transmission to the 'bot'
function collate_data(jsdata) {
  gopigo3_joystick.time_stamp = Number.parseFloat(jsdata.timestamp).toFixed();
  gopigo3_joystick.x_axis = Number.parseFloat(jsdata.axes[0]).toFixed(2);
  gopigo3_joystick.y_axis = Number.parseFloat(jsdata.axes[1]).toFixed(2);
  gopigo3_joystick.force =  Math.abs(Number.parseFloat(jsdata.axes[1]).toFixed(2));
  gopigo3_joystick.trigger_1 = jsdata.buttons[0].value;
  gopigo3_joystick.trigger_2 = jsdata.buttons[14].value;
  gopigo3_joystick.head_enable = jsdata.buttons[5].value;
  return (gopigo3_joystick)
}

//  Function "what_i_am_doing" takes the condition of the triggers and the position
//  of the controller and determines what the robot is, (i.e. "should be"), doing

function what_i_am_doing(gopigo3_joystick) {

//  If **EITHER** force = 0 **OR** trigger_1 has been released, the robot automatically
//  enters the "Stopped" state.
//  Note that the condition force = 0 compells the robot to stop, no matter what else may be happening.

  if (gopigo3_joystick.force == 0 || gopigo3_joystick.trigger_1 == 0) {
      gopigo3_joystick.motion_state = 'Stopped';
      gopigo3_joystick.angle_dir = 'Stopped';
      gopigo3_joystick.force = 0.00;
  }

//  If force is **NOT** zero, **AND** trigger_1 = 1 the robot *must* be moving, therefore the
//  signed magnitude of the Y axis determines the direction of motion.
//  If the Y-axis is < 0, the joystick is being pushed forward and if the Y-axis is > 0
//  the joystick is being pulled backward.
//
//  In both of these cases X-axis < 0 means motion to the left and X-axis > 0 means
//  motion to the right.
//
//  Note: we don't worry about the state of trigger_2, (turbo-speed) here,
//  that's taken care of back at the 'bot.
//
  else if (gopigo3_joystick.trigger_1 == 1 && gopigo3_joystick.force > 0) {  // robot is moving
    gopigo3_joystick.motion_state = 'Moving';

// At this point we know that the robot is moving, (trigger_1 = 1 and force > 0),
// and we've already grabbed the x and y axis values.
// The next step is to determine the direction of travel so we can display it

    if (gopigo3_joystick.y_axis < 0) { // robot is moving forward

//  We know the robot is moving forward, (y axis < 0),
//  therefore the question becomes "forward in what direction"?

      if (gopigo3_joystick.x_axis == 0) { // moving directly ahead
        gopigo3_joystick.angle_dir = 'Forward';
      }
      else if (gopigo3_joystick.x_axis > 0) {  // moving forward to the right
      gopigo3_joystick.angle_dir = 'Forward-Right';
      }
      else if (gopigo3_joystick.x_axis < 0) {  // moving foreard to the left
      gopigo3_joystick.angle_dir = 'Forward-Left';
      }
    }
//  If the Y axis value is > 0, the stick is being pulled backwards.
    else if (gopigo3_joystick.y_axis > 0) { // robot is moving bacxkward

//  This uses the same logic as the previous section, but in reverse.

      if (gopigo3_joystick.x_axis == 0) { // moving directly backward
        gopigo3_joystick.angle_dir = 'Backward';
      }
      else if (gopigo3_joystick.x_axis > 0) {  // moving backward to the right
        gopigo3_joystick.angle_dir = 'Backward-Right';
      }
      else if (gopigo3_joystick.x_axis < 0) {  // moving foreard to the left
        gopigo3_joystick.angle_dir = 'Backward-Left';
      }
    }
    else {  //  we should NEVER get here, but. . . . (wink!)
      gopigo3_joystick.motion_state = 'invalid condition\nin what_i_am_doing'
      gopigo3_joystick.force = 0  //  Force robot to stop.
    }
  }

//  Check for head motion.
//  In order for the head to be moved, the head-enable trigger must be pressed **AND** the main trigger
//  must be released.  IOW, head and body motion cannot occur at the same time. (this may change later)

  if (gopigo3_joystick.head_enable == 1 && gopigo3_joystick.trigger_1 == 0) {
    gopigo3_joystick.head_x_axis = gopigo3_joystick.x_axis
    gopigo3_joystick.head_y_axis = gopigo3_joystick.y_axis
  }
  return(gopigo3_joystick);
}

//  is_something_happening is a "spinning" function that waits for the timestamp to change.
//  This (hopefully) allows the browser to run at full speed, but doesn't clog the network.
//  Note that a noisy controller axis or button will totally defeat this.

function is_something_happening(jsdata, gopigo3_joystick) {
  var old_time = gopigo3_joystick.time_stamp
  while (old_time == Number.parseFloat(jsdata.timestamp).toFixed()) {
    requestAnimationFrame(is_something_happening(jsdata, gopigo3_joystick));
  }
  get_gamepad_data()
}

function send_data(gpg_data) {
  var query_string;
  console.log('gpg_data =', gpg_data);
  query_string = '?' + $.param(gpg_data);
  console.log('query_string =', query_string);
  $.post(server_address + query_string);
  return;
}

// Update the on-screen data
function setOnScreen(screen_data) {
  document.getElementById('controller_status').innerHTML = "Robot Controller Status: " + screen_data.controller_status;
  document.getElementById('motion_state').innerHTML = "Robot's Motion State: " + screen_data.motion_state;
  document.getElementById('angle_dir').innerHTML = "Robot's Direction: " + screen_data.angle_dir;
  document.getElementById('time_stamp').innerHTML = "Timestamp " + screen_data.time_stamp;
  document.getElementById('x_axis').innerHTML = "X-Axis: " + screen_data.x_axis;
  document.getElementById('y_axis').innerHTML = "Y-Axis: " + screen_data.y_axis;
  document.getElementById('head_x_axis').innerHTML = "Head's X-Axis: " + screen_data.head_x_axis;
  document.getElementById('head_y_axis').innerHTML = "Head's Y-Axis: " + screen_data.head_y_axis;
  document.getElementById('force').innerHTML = "Applied Force: " + screen_data.force;
  document.getElementById('trigger_1').innerHTML = "Trigger 1: " + screen_data.trigger_1;
  document.getElementById('trigger_2').innerHTML = "Trigger 2: " + screen_data.trigger_2;
  document.getElementById('head_enable').innerHTML = "Head Enable: " + screen_data.head_enable;
  return;
}

// function get_more_data() {  //  this is the data aquisition loop
//   requestAnimationFrame(get_gamepad_data);
//   return;
// }
