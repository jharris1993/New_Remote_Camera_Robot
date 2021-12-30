// keyboard.js
// used to attempt to implement keyboard event handling for my
// head servo test code.
'use strict';

// imported keyboard handler code I hope to modify

let document = document.getElementById('zone_joystick'),

document.addEventListener('keydown', (e) => {
  if (!e.repeat)
    logMessage(`Key "${e.key}" pressed  [event: keydown]`);
  else
    logMessage(`Key "${e.key}" repeating  [event: keydown]`);
});

document.addEventListener('beforeinput', (e) => {
  logMessage(`Key "${e.data}" about to be input  [event: beforeinput]`);
});

document.addEventListener('input', (e) => {
  logMessage(`Key "${e.data}" input  [event: input]`);
});

document.addEventListener('keyup', (e) => {
  logMessage(`Key "${e.key}" released  [event: keyup]`);
});

