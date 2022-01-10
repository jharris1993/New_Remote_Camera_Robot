# New Remote Camera Robot

This project is a modification of the original [Remote Camera Robot](https://https://github.com/DexterInd/GoPiGo3/tree/master/Projects/RemoteCameraRobot) project as developed by Dexter Industries for my GoPiGo-3 robot.

![](assets/20220108_203104_img1.jpg)

## Objectives:

1. Develop an application that will allow the GoPiGo robot to be used as a FPV robot using a joystick controller instead of a mouse/touchscreen.
   1. My experience with the original code using nipple.js as the controller showed me that there was an incredible lack of precision and control over the robot's movements.
   2. I am hoping to create a controller interface that will provide more delicate and precise control over the robot's movements and allow the POV to be changed by moving the camera on the robot's pan-and-tilt.
2. Learn how to implement both server-side and client-side web application programming.
   1. Can I effectively control and manage the web-data being sent from the browser to the robot?
   2. Can I create a method where the robot can return specific status information, (like battery voltage, processor temp, or whatever), that will be overlaid on the browser's screen?
3. Learn how to use the various programming tools efficiently and correctly.
   1. VS-code
      1. Remote development on the actual robot from within my Windows 10 laptop.
      2. Learn how to use the various VS Code features and extensions to help create and manage a project.
   2. Git/GitHub
      1. Learn how to manage and maintain a project on GitHub using Git and the Git extensions within VS Code.

## Challenges:

### Primary Limitations

1. My absolute lack of knowlege about just about every aspect of this project.
   1. This is my ***FIRST*** robotics project of ***ANY*** complexity.
   2. This represents my second or third project in Python, and is my first project of any significant complexity in the language.
   3. This represents my ***FIRST*** project of ***ANY*** complexity in JavaScript.
   4. This is my first "complex" project managed within GitHub.
   5. This is my first web-based project.
2. The technical landscape of the project is shifting under me as I am working on it.
   1. The security model for the gamepad API is changing on almost a daily basis.
      1. The gamepad API is now requiring a secure context, (*i.e.* a "HTTPS" context), in order to work.  Previously, any web context was valid.
   2. The security model for the browser itself is shifting almost as quickly.
      1. It was necessary for me to research and then include CORS (Cross Origin Resource Sharing) headers within the server code so that the browser was allowed to access the other resources needed for the project.
      2. Browser security is shifting rapidly to an almost fully locked-down security model where everyting will need to be served from a "secure" source via HTTPS.
   3. Updates to the robot's operating system have mandated changes to the project, or changes to the robot's configuration to accomodate the project.

### Coding Challenges

1. The gamepad API doesn't have a generic event for joystick activity.
   1. The gamepad browser API was, (apparently), designed to be used for interfacing to ***games*** within the browser so the primary way of getting information is to poll the gamepad using the requestAnimationFrame() function which loops every v_sync interval
   2. The result of all this is that it is very difficult to manage gamepad activity in a server-based context as the server gets flooded with responses from the browser.
      1. I can regulate the amount of data being sent to the server by looping within the browser script waiting for the controller.time_stamp to increment.  This causes the browser to become sluggish or hang.
      2. I can delegate all the filtering to the server, wich wasts resources on the robot, slowing things down.
      3. My current plan of attack is to create a "web worker" - a separate process - that will handle polling the gamepad controller interface and then notify the main process when someting happens.

EOF.
