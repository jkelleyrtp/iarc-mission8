import math

import rospy
import tf
import tf.transformations
from geometry_msgs.msg import Twist, PoseStamped, Pose, Point, Quaternion
from iarc_arbiter.msg import RegisterBehavior, VelAlt
from iarc_main.msg import Roomba
from std_msgs.msg import String, Empty, Header

try:
    from ardrone_autonomy.msg import Navdata
except ImportError:
    rospy.logwarn("Unable to import ardrone_autonomy, assuming running on PX4")
    Navdata = None


class Drone:
    DEFAULT_HEIGHT = 1.5

    def __init__(self, tfl=None):
        """
        :type tfl: tf.TransformListener
        """
        rospy.loginfo("name: {}".format(rospy.get_name()))

        if rospy.get_name().endswith('/unnamed'):
            # Initialize the node
            rospy.init_node('controller', anonymous=True)
            rospy.sleep(0.2)

            # rospy.logwarn('initialing ROS node in Drone object')

        # World state
        self._remembers_flying = False

        # Remembered control state
        self.last_height = 0.0

        self.prev_target_facing_angle = None  # in radian

        self.FRAME_ID = "base_link"

        if tfl is None:
            self.tf = tf.TransformListener()
            rospy.sleep(1.0)
        else:
            self.tf = tfl

        self.posPub = rospy.Publisher('/forebrain/cmd_pos', PoseStamped, queue_size=0)
        self.velPub = rospy.Publisher('/forebrain/cmd_vel', Twist, queue_size=0)
        self.takeoffPub = rospy.Publisher('/forebrain/cmd_takeoff', Empty, queue_size=0)
        self.landPub = rospy.Publisher('/forebrain/cmd_land', Empty, queue_size=0)
        self.velAltPub = rospy.Publisher('/forebrain/cmd_vel_alt', VelAlt, queue_size=0)

        rospy.Publisher('/arbiter/register', RegisterBehavior, latch=True, queue_size=10).publish(
            name='forebrain', fast=True)
        rospy.sleep(0.1)
        rospy.Publisher('/arbiter/activate_behavior', String, latch=True, queue_size=10).publish(
            'forebrain')

        self.navdata = None
        if Navdata is not None:
            rospy.Subscriber('/ardrone/navdata', Navdata, self._on_navdata)

    def is_flying(self):
        """
        Tells whether the drone is currently flying. That includes the state where it is in the process
        of landing, but not the state where it is in the process of taking off.
        :return (Bool): is the drone flying?
        """
        if self.navdata is not None:
            # List of states taken from
            # http://ardrone-autonomy.readthedocs.io/en/latest/reading.html#legacy-navigation-data
            # "flying" = Flying or Hovering or Landing or Looping
            return self.navdata.state in [3, 7, 4, 8, 9]
        else:
            return self._remembers_flying

    def takeoff(self, height=1.5, tol=0.2):
        """
        Commands the drone to takeoff from ground level, and blocks until it has done so.
        :param (float) height: Height in meters
        :param (float) tol: Tolerance to desired height to wait until reaching. Set to 0 to disable.
        :return: None
        """
        self.last_height = height

        self.takeoffPub.publish(Empty())

        rospy.sleep(0.1)

        if tol > 0:
            r = rospy.Rate(10)
            while height - self.get_altitude() > tol and not rospy.is_shutdown():
                self.hover(time=0, height=height)
                r.sleep()
            rospy.loginfo("Drone reached height of {} meters, takeoff finished".format(self.get_altitude()))

        self._remembers_flying = True

    def land(self, block=True):
        """
        Commands the drone to land on the ground. Directly commands the low-level controls,
        and might need changes as hardware gets upgraded.
        :param (bool) block: Wait until vehicle reaches ground?
        :return: None
        """
        self.last_height = 0

        self.landPub.publish(Empty())

        rospy.sleep(0.1)

        if block:
            r = rospy.Rate(10)
            while self.get_altitude() > 0.2 and not rospy.is_shutdown():
                self.landPub.publish(Empty())
                r.sleep()
            rospy.sleep(0.5)

        self._remembers_flying = False

    def hover(self, time=0, height=None):
        """
        Publishes 0 velocity for the given duration
        TODO: Store the starting position, and stay there
        :param (float | rospy.Duration) time: If nonzero, hovers for this amount of time.
        :param height:
        :return:
        """
        if height is None:
            height = self.last_height
        else:
            self.last_height = height

        if type(time) != rospy.Duration:
            time = rospy.Duration.from_sec(time)

        # TODO: Consider using position-based hovering in more situations
        if time.to_sec() < 1.0:
            # For short duration hovers, just aim for 0 velocity
            self.velAltPub.publish(VelAlt(height=height))
            rospy.sleep(time.to_sec())
            return
        else:
            # For long duration hovers, try to actively stay in the same place
            hover_start_time = rospy.Time.now()

            start_pos = self.get_pos('odom')
            start_pos.pose.position.z = height

            # Always use the latest available information
            start_pos.header.stamp = rospy.Time(0)

            r = rospy.Rate(10)
            self.posPub.publish(start_pos)
            while rospy.Time.now() - hover_start_time < time:
                r.sleep()
                self.posPub.publish(start_pos)

    def move_to(self, des_x=0.0, des_y=0.0, frame='map', height=0.0, tol=0.4):
        """
        Tells the drone to move to a specific position on the field, and blocks until the drone is
        within tol of the target, counting vertical and horizontal distance
        :param des_x:
        :param des_y:
        :param frame:
        :param height:
        :param tol:
        :return:
        """

        if height == 0.0:
            height = self.last_height

        r = rospy.Rate(20)
        while not rospy.is_shutdown():
            rel_pos = self.get_pos(frame).pose.position
            dist = math.sqrt(
                (rel_pos.x - des_x) ** 2 +
                (rel_pos.y - des_y) ** 2 +
                (rel_pos.z - height) ** 2)
            if dist <= tol:
                break

            self.move_towards(des_x, des_y, frame, height)

            r.sleep()

    def move_towards(self, des_x=0.0, des_y=0.0, frame='map', height=None):
        """
        Tells the drone to begin moving towards a specific position on the field, then returns
        :param height: Flight altitude, meters. Defaults to previously commanded height.
        :param frame: The tf frame associated with the target
        :param des_x: desired position x
        :param des_y: desired position y
        """

        if height is None:
            height = self.last_height
        else:
            self.last_height = height

        pose_stamped = PoseStamped()
        pose_stamped.pose.position.x = des_x
        pose_stamped.pose.position.y = des_y
        pose_stamped.pose.position.z = height
        pose_stamped.header.frame_id = frame

        self.posPub.publish(pose_stamped)

    def get_pos(self, frame='map'):
        """
        Gets the position of the drone in the map (or relative to some other coordinate frame)

        :param frame: The world frame in which to return the result
        :return (PoseStamped): The position of the drone at the latest available time
        """
        time = None
        while not time and not rospy.is_shutdown():
            try:
                time = self.tf.getLatestCommonTime(frame, self.FRAME_ID)
            except:
                rospy.sleep(0.5)
                rospy.logwarn("Frame missing, delaying...")

        position, quaternion = self.tf.lookupTransform(frame, self.FRAME_ID, time)

        return PoseStamped(
            header=Header(
                stamp=time,
                frame_id=frame
            ),
            pose=Pose(
                position=Point(
                    x=position[0], y=position[1], z=position[2]
                ),
                orientation=Quaternion(
                    x=quaternion[0], y=quaternion[1], z=quaternion[2], w=quaternion[3]
                )
            )
        )

    def get_altitude(self):
        return self.get_pos(frame='odom').pose.position.z

    def distance_from(self, frame):
        """
        Returns the linear distance along the ground between the robot and the origin of the provided TF frame.
        TODO: Allow PoseStamped as imput, rather than just using the origin.
        :param (str) frame: The TF frame to measure to
        :return:
        """
        linear = self.get_pos(frame).pose.linear

        return math.sqrt(linear.x ** 2 + linear.y ** 2)

    def _on_navdata(self, msg):
        """
        :param (Navdata) msg:
        """
        self.navdata = msg

