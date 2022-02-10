// @ts-check
//
//  New Remote Camera Robot
//  This is the broser-side script that allows for moving the GoPiGo3
//  robot with a conventional joystick.
//

// Global variables
var server_address = window.location.protocol + "//" + window.location.host + "/robot";
var joystick_data = [];
var js = [];

//  Formal definition of "gopigo3_joystick"
//  gopigo3_joystick is the structure that contains all the joystick elements of interest to the GoPiGo robot
//  This collects them together in one place so they can be used, changed, monitored, and ultimately
//  transmitted to the robot as a serialized parameter string.
var gopigo3_joystick = {
    controller_status: 'Disconnected',
    motion_state: 'Waiting for Joystick',
    angle_dir: 'None',
    time_stamp: 0,  // a large integer that, (sometimes), becomes a float (shrug shoulders)
    x_axis: 0.00,  //  x-axis < 0, joystick pushed left - x-axis > 0, joystick pushed right
    y_axis: 0.00,  // y-axis < 0, joystick pushed forward - y-axis > 0 , joystick pullled back
    head_x_axis: 0.00,  //  head x and y axes mirror the joystick x and y axes
    head_y_axis: 0.00,  //  if the pinky-switch, (head motion enable), is pressed
    force: 0.00,  //  force is the absolute value of the y-axis deflection
    trigger_1: 0,   // Partial primary trigger press (motion enabled)
    trigger_2: 0,   // Full primary trigger press  (faster speed - not yet implemented)
    head_enable: 0  // Pinky-switch press  (enable joystick to move head)
};

//  Formal definition of old_event_context
//  old_event_context allows values for old_time_stamp and old_trigger_state to persist across functon calls
var old_event_context = {
    old_time_stamp: 0,  // set sane initial values for both variables
    old_trigger_state: 0
};

//  Event Listeners

window.addEventListener("gamepadconnected", (event) => {
    // @ts-ignore  Ignore "gamepad" missing class properties for things like push, pop, etc.
    js = event.gamepad;
    gamepad_connected();  // Gamepad is now connected, set up the data structure
    //  and capture the state of the timestamp.
    old_event_context.old_time_stamp = Number.parseFloat((gopigo3_joystick.time_stamp).toFixed(0))
});

window.addEventListener("gamepaddisconnected", (event) => {
    gopigo3_joystick.controller_status = "Disconnected"; // Joystick disconnected, so set state to "diusconnected"
    gopigo3_joystick.motion_state = 'Waiting for Joystick';
    gamepad_disconnected(); // clear out stale data
});

window.addEventListener('keydown', (event) => {
    var keyName = event.key;
    gopigo3_joystick.motion_state = keyName;
    //  We have a keypress so we send it to the robot to be handled.
    send_data();
});

//  Gamepad connect and disconnect event handlers.

// gamepad_connected is called by the event handler when a joystick
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

    //  Now that we've initialised the gopigo3_joystick structure, we send it to the robot
    send_data();

    //  Now that a joystick is connected, we start scanning for data.
    get_game_loop(); //  Kick-off the actual handling of gamepad events
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
    send_data()  // send it to the robot
    get_game_loop(); // continue service loop
    return;
};

//  The actual gamepad data collection routines follow

//  Collate data collects all the data, normalizes it, packages it,
//  and prepares it for transmission to the 'bot'
function collate_data(jsdata) {
    gopigo3_joystick.time_stamp = Number((jsdata.timestamp).toFixed(0));
    gopigo3_joystick.x_axis = Number.parseFloat((jsdata.axes[0]).toFixed(2));
    gopigo3_joystick.y_axis = Number.parseFloat((jsdata.axes[1]).toFixed(2));
    gopigo3_joystick.force =  Math.abs(gopigo3_joystick.y_axis);
    gopigo3_joystick.trigger_1 = Number((jsdata.buttons[0].value).toFixed(0));
    gopigo3_joystick.trigger_2 = Number((jsdata.buttons[14].value).toFixed(0));
    gopigo3_joystick.head_enable = Number((jsdata.buttons[5].value).toFixed(0));

//  Make the x_axis less touchy by enforcing a "dead-zone"
    if (Math.abs(gopigo3_joystick.x_axis) < 0.2) {
        gopigo3_joystick.x_axis = 0.00
    }
    return;
}

//  Function "what_i_am_doing" takes the condition of the triggers and
//  the position of the controller and determines what the robot is,
//  (i.e. "should be"), doing.
//  (Is the robot stopped?  Moving?  If so, where and in what direction?
//  Should the head be moving?)

//  Note that this is primarily for documentation purposes for the on-screen display

function what_i_am_doing() {

//  If **EITHER** force = 0 **OR** trigger_1 has been released, the
//  robot automatically enters the "Stopped" state.
//  Note that the condition force = 0 compells the robot to stop,
//  no matter what else may be happening.

    if (gopigo3_joystick.force == 0.00 || gopigo3_joystick.trigger_1 == 0) {
        gopigo3_joystick.motion_state = 'Stopped';
        gopigo3_joystick.angle_dir = 'Stopped';
        gopigo3_joystick.force = 0.00;
    }  //  end "robot is not moving"

    //  If force is **NOT** zero, **AND** trigger_1 = 1 the robot *must*
    //  be moving, therefore the signed magnitude of the Y axis
    //  determines the direction of motion.
    //  If the Y-axis is < 0, the joystick is being pushed forward and
    //  if the Y-axis is > 0, the joystick is being pulled backward.
    //
    //  In both of these cases X-axis < 0 means motion to the left and
    //  X-axis > 0 means motion to the right.
    //
    //  Note: we don't worry about the state of trigger_2, (turbo-speed)
    //  here, that's taken care of back at the 'bot.
    //
    else if (gopigo3_joystick.trigger_1 == 1 && gopigo3_joystick.force > 0.00) {  // robot is moving
        gopigo3_joystick.motion_state = 'Moving';

    //  At this point we know that the robot is moving,
    //  (trigger_1 = 1 and force > 0), and we've already grabbed the x
    //  and y axis values. The next step is to determine the direction
    //  of travel so we can display it.

        if (gopigo3_joystick.y_axis < 0.00) { // robot is moving forward

        //  We know the robot is moving forward, (y axis < 0),
        //  therefore the question becomes "forward in what direction"?

            if (gopigo3_joystick.x_axis == 0.00) { // moving directly ahead
                gopigo3_joystick.angle_dir = 'Directly Forward';
            }
            else if (gopigo3_joystick.x_axis > 0.00) {  // moving forward to the right
                gopigo3_joystick.angle_dir = 'Forward-Right';
            }
            else if (gopigo3_joystick.x_axis < 0.00) {  // moving foreard to the left
                gopigo3_joystick.angle_dir = 'Forward-Left';
            }
        }  // end "robot is moving forward"

        //  If the Y axis value is > 0.00, the stick is being pulled backwards.
        else if (gopigo3_joystick.y_axis > 0.00) { // robot is moving bacxkward

        //  This uses the same logic as the previous section, but in reverse.

            if (gopigo3_joystick.x_axis == 0.00) { // moving directly backward
                gopigo3_joystick.angle_dir = 'Directly Backward';
            }
            else if (gopigo3_joystick.x_axis > 0.00) {  // moving backward to the right
            gopigo3_joystick.angle_dir = 'Backward-Right';
            }
            else if (gopigo3_joystick.x_axis < 0.00) {  // moving foreard to the left
            gopigo3_joystick.angle_dir = 'Backward-Left';
            }
        }  //  end "robot is moving backward"

        else {  //  we should NEVER get here, but. . . . (wink!)
            gopigo3_joystick.motion_state = 'invalid condition\nin what_i_am_doing'
            gopigo3_joystick.force = 0.00  //  Force robot to stop.
        }
    }  // end "robot is moving" motion control logic

    //  Check for head motion.
    //  In order for the head to be moved, the head-enable trigger must
    //  be pressed **AND** the main trigger must be released.
    //  IOW, head and body motion cannot occur at the same time.
    //  (this may change later)

    if (gopigo3_joystick.head_enable == 1 && gopigo3_joystick.trigger_1 == 0) {
        gopigo3_joystick.head_x_axis = gopigo3_joystick.x_axis
        gopigo3_joystick.head_y_axis = gopigo3_joystick.y_axis
        // TODO:  Implement head motion via joystick.
    }  //  end "head motion" logic
    return;
}  //  end function what_i_am_doing (motion control logic)

//  is_someting_happening is my attempt to create a joystick "event" when "something interesting" happens.
//  "someting interesting" = any joystick movement if either enabling trigger is pressed
//  or, if a previously pressed trigger has been released.
//  Otherwise, no data should be sent.
function is_something_happening() {
    if (gopigo3_joystick.trigger_1 == 1 || gopigo3_joystick.head_enable == 1) {  //  Has an enabling trigger event happened?
        if (old_event_context.old_time_stamp != Number.parseFloat((gopigo3_joystick.time_stamp).toFixed())) {  // and, has the timestamp changed?
            send_data()  //  then, send data to the robot and. . .
            old_event_context.old_time_stamp = Number.parseFloat((gopigo3_joystick.time_stamp).toFixed())  //  Save current time_stamp to compare to future changes
            old_event_context.old_trigger_state = 1  // record trigger was pressed
        }
    }
    else if (old_event_context.old_trigger_state == 1) {  // current trigger value MUST be zero here - old_trigger_state = 1 means a trigger has changed
        send_data()  // send the trigger release event
        old_event_context.old_time_stamp = gopigo3_joystick.time_stamp  //  Save current time_stamp to compare to future changes
        old_event_context.old_trigger_state = 0  // record the fact that the trigger was released
    }  // else. . . there's nothing interestng to say so we just return.
    return;
}

// @ts-ignore
var send_throttled_data = throttle(function(server_address, query_string) {
    $.post(server_address + query_string);
}, 250);

//  This is what actually serializes and sends the data to the robot.
function send_data() {
    var query_string = '';
    query_string = '?' + $.param(gopigo3_joystick);
    console.log('gpg_data =', gopigo3_joystick);
    console.log('query_string =', query_string);
    send_throttled_data(server_address, query_string);
    return;
}

// Update the on-screen data window
function set_on_screen_data() {
    document.getElementById('motion_state').innerHTML = "Robot's Motion State: " + gopigo3_joystick.motion_state;
    document.getElementById('angle_dir').innerHTML = "Robot's Direction: " + gopigo3_joystick.angle_dir;
    document.getElementById('time_stamp').innerHTML = "Timestamp " + gopigo3_joystick.time_stamp;
    document.getElementById('force').innerHTML = "Applied Force: " + gopigo3_joystick.force;
    return;
}

//  Function get_gamepad_data is the main "game loop" function that organizes and calls all the other
//  functions that are needed to make this script work.
function  get_gamepad_data() {
    // @ts-ignore  Ignore "navigator.webkit" typwscript error
    var js = (navigator.getGamepads && navigator.getGamepads()) || (navigator.webkitGetGamepads && navigator.webkitGetGamepads());
    collate_data(js[0]);  //  Collect variable data to be sent

    //  Look at the data returned and describe what the robot should be doing.
    //  This is primarily "documentation" for the on-screen window and might be removed later.
    what_i_am_doing()  // Collect motion status

    // Check for joystick activity and send updated data if true
    is_something_happening();

    // Update the on-screen data with whatever the joystick is doing.
    set_on_screen_data();

    get_game_loop(); // continue the requestAnimationFrame loop
    return;
}

//  In a stand-alone browser implementation of a gamepad driven game,
//  *this* represents the "game loop".

function get_game_loop() {  //  this is the "game loop"
        // @ts-ignore  Ignore typescript error passing function instead of just a number
    setTimeout(requestAnimationFrame(get_gamepad_data), 125);
    return;
}
