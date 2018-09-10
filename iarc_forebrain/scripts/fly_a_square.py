# Hello! As you can see, this line starts with a hashtag. That creates something called a "comment"
# in programming. Comments are ignored by the code interpreter so you can write whatever you want
# without breaking your program.

# I'll walk you through this example file that can fly the drone in a square.


# So first, you should be relieved to know that we do not expect you to code the drone from
# scratch. This is due to beautiful things we have in Python called "modules". A module is basically
# a bunch of code that SOMEONE ELSE wrote that you can automatically import into your own program.
# For example, people have written hundreds of lines of code to make a drone take off from the ground.
# Is it reasonable to expect you to copy/paste those hundreds of lines of code into your program
# every time you need to make a drone take off? NO!!!!
# Programming is awesome because people can package their code into modules. Modules are condensed
# pieces of prewritten code that we can use.

# Here we import something from the Drone module (we wrote this on IARC last year - you're welcome.)
# So now to make a drone takeoff it's literally one line of code -- which you'll see very shortly.
from Drone import Drone
import rospy # This is another module we need. Don't worry about this for now.

# Create a drone object. You can name your drone anything you want (I've named my drone Fred)

fred = Drone()

# First thing that Fred needs to do is take off from the ground. To make him fly we command him like this:

fred.takeoff() #Told you it was one line!!

# This command makes Fred fly upwards to an altitude of 1.5 meters. He will stay there if you dont give him
# another command! Tell him to move forward next:

fred.move_to(1.0, 0.0, 'launch')

# So what does that command mean? Fred recognizes move_to() as a command but requires
# 3 "parameters" (inputs) to customize the exact instructions we want to give him.
# fred.move_to(1.0, 0.0, 'launch') tells fred to move to position (1.0, 0.0) on a grid that
# is centered on his 'launch' position. This command will make him move 1 meter in the
# x-direction from his launch position,
# If you wanted him to move the opposite direction, you can use the command fred.move_to(-1.0, 0.0, 'launch')

# At this point in the code, Fred has moved to position (1.0, 0.0). Good job, Fred.
# Now let's move again. It's been forever since I've taken geometry in high school but if I remember
# correctly, to create a square we can move to positions (1.0, 1.0), (0.0, 1.0), then back to the launch position, (0.0, 0.0).

fred.move_to(1.0, 1.0, 'launch')
fred.move_to(0.0, 1.0, 'launch')
fred.move_to(0.0, 0.0, 'launch')

# Fred has completed the square. Woo!
# Now he needs a break. Let's tell him to hover in place for 3 seconds before landing:

fred.hover(3)
fred.land()