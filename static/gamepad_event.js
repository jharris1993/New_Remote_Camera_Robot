/*
gamepad_event.js
This script is a "worker" script to handle joystick/gamepad events and despatch them to the main script.

The big disadvantage with the gamepad API is that gamepads only have two true events:
gamepadconnected and gamepaddisconnected - anything else that happens after that is not event driven
as the expected use-case was a in-borwser game running via the requestAnimationFrame() loop.

This becomes a problem if you're using the gamepad for something other than a game, (such as a robot
or a some kind of hardware is being controlled), where there are constantly recurring
calls to the gamepad and data is being returned every v_sync interval.

The solution is some kind of generic "gamepad" event that triggers *ONLY* when there's a change in
the gamepad's status.

The idea behind this is that I am going to try to encapsulate the joystick events inside
this worker script and have it pass message events back to the main one.
*/

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
