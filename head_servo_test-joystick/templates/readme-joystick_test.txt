joystick_test.html

This file is an example/test file whose entire function is to determine
how to capture and use the various readings and attributes of the connected
joystick.

axis 0 is the left-right axis such that:
*  Axis 0 represents the angular deviation of the robot
   to the right or left.
*  x0 < 0 is a right turn
*  x0 > 0 is a left turn.
*  x0 = 0 represents no angular deviation at all.
   The trigonometric ratio between x0 and x1 determines the "sharpness"
   of the turn.

axis 1 is the forward-backward axis such that:
*  Axis 1 represents the velocity of the robot. (speed of motion)
*  x1 < 0 is forward motion
*  x1 > 0 is backward motion
*  x1 = 0 represents no forward or backward velocity at all.
*  The trigonometric ratio of x0 and x1 determines if the forward
   or backward path is curved or straight.

The special case where both x0 and x1 = 0 is the stopped state
where there is no motion in any direction.  This is further
guaranteed by setting all angles and velocities to zero.

Theory:
Since the robot can move in a combination of forward/backward
and right/left at the same time, it is necessary to determine
the speed, along with ratio of the speeds, of the two wheels
in order to determine both direction of travel and angular
deviation in that direction.

Case 1:
   The speed of both wheels is the same.
   (i.e. x0 = 0 when x1 != 0)
   *  This represents movement directly forward or backward.
   *  The speed of the two wheels represents the velocity of
      the robot.
Case 2:
   The speed of the two wheels are *NOT* the same.
   The magnitude of x1 determines if the turn is a moving
   turn, (x1 !=0), or a turn in-place, (x1 = 0).
   *  This represents a turn to the right or the left.
   *  The ratio of the speeds of the two wheels
      determines the degree of angular deviation
      relative to the velocity forward or backward.
      (i.e. The "sharpness" of the turn.)

To accomplish this, we need to know three things:
*  The forward or backward velocity of the robot
   if any, (i.e. The magnitude of x1).
*  The "force" of the turn, (i.e. The magnitude of x0).
*  The *magnitude* of the angular deviation, right or left.
   Note that we don't care what the actual *angle* of the
   left or right deviation might be, just the magnitude,
   so we can calculate the ratio of the speeds of the two wheels.

To determine both the angular deviation and the direction of travel,
we need to know the percentage ratio of one wheel to the other.
We can simplify this by knowing that in any turn, the wheel on the
"inside" of the turn is always moving more slowly than the wheel
on the "outside" of the turn.

Whe can calculate this ratio by knowing that the two motion axes
constitute a right triangle, and the length of the hypotenuse is
based on the ratio of the magnitudes of the x0 and x1 axes.

The  actual percentage ratio between the two wheels can be found
by taking the cosine of the included angle of x0 and the hypotenuse.
This will be a number between 1 and 0, such that a slight angular
deviation to the right or left will produce cosines nearly equal to
one and the greater the angular deviation, the smaller the cosine
and the greater the ratio of the two wheels.

For example:
*  If the robot is moving streight ahead, the angle between x0 and x1
   is 90 degrees, and the cosine of 90 degrees is 1.  Therefore the
   ratio of the two wheels is 100%/100% with the value that "100%"
   represents is the magnitude of the x1 axis, positive or negative.
*  If the robot is making a turn, the angle between x0 and x1 will be
   less than 90 degrees such that the ratio of one wheel to the other
   will be a deimal fraction of the speed of the wheel on the outside
   of the turn.

   Note that as the angle of the hypotenuse of that
   right triangle approaches the x0 axis, the slower the inside wheel
   must turn until the angle = 0, where the inside wheel will be
   completely stopped.

*  In order to calculate the decimal fraction of the wheel speed that
   the inside wheel must be reduced by, based on the angle between the
   hypotenuse and the x0 axis is the cosine of that angle.  Since the
   magnitude of the cosine becomes smaller as that angle becomes
   smaller, the percentage of the velocity of the outside wheel also
   becomes smaller - providing exactly the effect we want.

We can calculate the cosine easily, without using triginometric functions,
by dividing the length of the x0 axis vector by the length of the hypotenuse
as calculated using the Pathgorean Therom - sqrt((|x0|**2) = (|x1|**2)).

Optimization:  Multiplication is *MUCH* faster than the power function,
so we can re-write the Pathagorean Therom as sqrt((x0 * x0) + (x1 * x1)).
This provides the following advantages:
*  Multiplication is aproximately 10x the speed of the sqrt()/ power function
   (See Stack Overflow article at
   https://stackoverflow.com/questions/327002/which-is-faster-in-python-x-5-or-math-sqrtx).
*  Squaring a number guarantees the number will *always* be positive,
   regardless of the original sign, eliminating the need for the
   absolute value function/operator.
*  This will provide an execution speed advantage of about 20x,
   (10x + 10x because we avoided the power function twice), along with
   the advantage of avoiding the absolute value function/operator
   four times.
