//  Joystick Data Test
//  This should return data to Joystick_Data_Test.html
//
//      "use strict";  // enforces "strict" type and syntax checking (i.e. no sloppy code allowed!)

      var server_address = window.location.protocol + "//" + window.location.host + "/robot";
      var joystick_data
      var js

      //  Formal definition of "gopigo3_orientation"
      var gopigo3_orientation = {
        controller_status: 'Disconnected',
        motion_state: 'Waiting for Joystick',
        angle_dir: 'Stopped',
        x_axis: 0.00,
        y_axis: 0.00,
        head_x_axis: 0.00,
        head_y_axis: 0.00,
        force: 0.00,
        trigger_1: 0,   // Partial trigger press (slow speed)
        trigger_2: 0,   // Full trigger press  (faster speed)
        head_enable: 0  // Pinky-switch press  (enable joystick to move head)
      };

      window.addEventListener("gamepadconnected", (event) => {
        js = event.gamepad;
//        console.log("A gamepad was connected:");
        gamepad_connected();  // Gamepad is now connected
        get_data();  // Tell the robot and start accumulating data
      });

      window.addEventListener("gamepaddisconnected", (event) => {
//        console.log("A gamepad was disconnected:");
        gopigo3_orientation.controller_status = "Disconnected"; // Joystick disconnected, so set state to "diusconnected"
        gopigo3_orientation.motion_state = 'Waiting for Joystick';
//        console.log(event.gamepad);
        gamepad_disconnected(); // clear out stale data
        get_data(); // send it to the server
      });

      function  get_gamepad_data() {
        js = (navigator.getGamepads && navigator.getGamepads()) || (navigator.webkitGetGamepads && navigator.webkitGetGamepads());
//        console.log("\nthe 'navigator.getGamepads()' (js) value is:");
        // console.log(js);

        // console.log("js[0]");
        // console.log(js[0]);

        collate_data(js[0]);  //  Collect variable data to be sent
        what_am_i_doing(gopigo3_orientation)  // Collect motion status
        send_data(gopigo3_orientation);  // Send normalized data to 'bot'

        // Update the on-screen data with the nrmalized data
        setOnScreen(gopigo3_orientation);

        // Here we loop on the requestAnimationFrame after a timeout (in ms)
        // to prevent saturating the network every 1/60th second (or faster)
        // depending on the capabilities of the monitor/browser being used.
        setTimeout(get_data, 125);
      return;
      }

// gamepad_connected is called during the event handling when a joystick
// is connected, and initializes the gamepad data to a sane "connected" value
      function gamepad_connected() {
        gopigo3_orientation.controller_status = 'Connected'; // Joystick connected but not moving
        gopigo3_orientation.motion_state = 'Stopped';
        gopigo3_orientation.angle_dir = 'Stopped';
        gopigo3_orientation.x_axis = 0.00;
        gopigo3_orientation.y_axis = 0.00;
        gopigo3_orientation.head_x_axis = 0.00;
        gopigo3_orientation.head_y_axis = 0.00;
        gopigo3_orientation.force = 0.00;
        gopigo3_orientation.trigger_1 = 0;
        gopigo3_orientation.trigger_2 = 0;
        gopigo3_orientation.head_enable = 0;
        send_data(gopigo3_orientation);
      }

      function gamepad_disconnected() {
        gopigo3_orientation.controller_status = 'Disconnected';
        gopigo3_orientation.motion_state = 'Waiting for Joystick';
        gopigo3_orientation.angle_dir = 'Stopped';
        gopigo3_orientation.x_axis = 0.00;
        gopigo3_orientation.y_axis = 0.00;
        gopigo3_orientation.head_x_axis = 0.00;
        gopigo3_orientation.head_y_axis = 0.00;
        gopigo3_orientation.force = 0.00;
        gopigo3_orientation.trigger_1 = 0;
        gopigo3_orientation.trigger_2 = 0;
        gopigo3_orientation.head_enable = 0;
        send_data(gopigo3_orientation);
      };

//  Collate data collects all the data, normalizes it, packages it, and prepares
//  for transmission to the 'bot'
      function collate_data(jsdata) {
        gopigo3_orientation.head_x_axis = Number.parseFloat(jsdata.axes[4]).toFixed(2);
        gopigo3_orientation.head_y_axis = Number.parseFloat(jsdata.axes[3]).toFixed(2);
        gopigo3_orientation.force =  Math.abs(Number.parseFloat(jsdata.axes[1]).toFixed(2));
        gopigo3_orientation.trigger_1 = jsdata.buttons[0].value;
        gopigo3_orientation.trigger_2 = jsdata.buttons[14].value;
        gopigo3_orientation.head_enable = jsdata.buttons[5].value;
        return (gopigo3_orientation)
      }

      function what_am_i_doing(gopigo3_orientation) {
        if (gopigo3_orientation.force == 0) {  // Robot is obviously stopped here as force must = 0
//            gopigo3_orientation.state = 'Stopped';  // stopped so flush all variables
            gopigo3_orientation.motion_state = 'Stopped';
            gopigo3_orientation.angle_dir = 'Stopped';
            gopigo3_orientation.x_axis = 0.00;
            gopigo3_orientation.y_axis = 0.00;
            gopigo3_orientation.head_x_axis = 0.00;
            gopigo3_orientation.head_y_axis = 0.00;
            gopigo3_orientation.force = 0.00;
        }


//  If force is *not* zero, the robot *must* be moving, therefore the
//  signed magnitude of the Y axis determines the direction of motion.
//  If the Y-axis is < 0, the joystick is being pushed forward.
//
//  In both of these cases X-axis > 0 means motion to the left and X-axis < 0 means
//  motion to the right.
        else if (gopigo3_orientation.trigger_1 == 1 && gopigo3_orientation.force > 0) {  // robot is moving
        //          gopigo3_orientation.state = 'Moving';
          gopigo3_orientation.motion_state = 'Moving';
          gopigo3_orientation.x_axis = Number.parseFloat(jsdata.axes[0]).toFixed(2);
          gopigo3_orientation.y_axis = Number.parseFloat(jsdata.axes[1]).toFixed(2);
 
          if (gopigo3_orientation.y_axis < 0) { // moving forward
            if (gopigo3_orientation.x_axis == 0) { // moving directly ahead
              gopigo3_orientation.angle_dir = 'Forward';
            }
            else if (gopigo3_orientation.x_axis > 0) {  // moving forward to the right
            gopigo3_orientation.angle_dir = 'Forward-Right';
            }
            else if (gopigo3_orientation.x_axis < 0) {  // moving foreard to the left
            gopigo3_orientation.angle_dir = 'Forward-Left';
            }
          }  
//  If the Y axis value is > 0, the stick is being pulled backwards.
          else if (gopigo3_orientation.y_axis > 0) { // moving bacxkward
            if (gopigo3_orientation.x_axis == 0) { // moving directly backward
              gopigo3_orientation.angle_dir = 'Backward';
            }
            else if (gopigo3_orientation.x_axis > 0) {  // moving backward to the right
              gopigo3_orientation.angle_dir = 'Backward-Right';
            }
            else if (gopigo3_orientation.x_axis < 0) {  // moving foreard to the left
              gopigo3_orientation.angle_dir = 'Backward-Left';
            }
          }
        }
        return(gopigo3_orientation);
      }

      function send_data(gpg_data) {
        console.log('gpg_data =', gpg_data);
        query_string = '?' + $.param(gpg_data);
        console.log('query_string =', query_string);
        $.post(server_address + query_string);
      }

      // Update the on-screen data
      function setOnScreen(screen_data) {
        document.getElementById('controller_status').innerHTML = "Robot Controller Status: " + screen_data.controller_status;
        document.getElementById('motion_state').innerHTML = "Robot's Motion State: " + screen_data.motion_state;
        document.getElementById('angle_dir').innerHTML = "Robot's Direction: " + screen_data.angle_dir;
        document.getElementById('x_axis').innerHTML = "X-Axis: " + screen_data.x_axis;
        document.getElementById('y_axis').innerHTML = "Y-Axis: " + screen_data.y_axis;
        document.getElementById('head_x_axis').innerHTML = "Head's X-Axis: " + screen_data.head_x_axis;
        document.getElementById('head_y_axis').innerHTML = "Head's Y-Axis: " + screen_data.head_y_axis;
        document.getElementById('force').innerHTML = "Applied Force: " + screen_data.force;
        document.getElementById('trigger_1').innerHTML = "Trigger 1: " + screen_data.trigger_1;
        document.getElementById('trigger_2').innerHTML = "Trigger 2: " + screen_data.trigger_2;
        document.getElementById('head_enable').innerHTML = "Head Enable: " + screen_data.head_enable;
      }

      function get_data() {
        requestAnimationFrame(get_gamepad_data);
      }

