#!/usr/bin/env python


"""
Based off of Winter Guerra's potential fields node.
"""

import rospy

from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import PointStamped
from solace.msg import DriveCommand

from rospy.numpy_msg import numpy_msg
import numpy as np
import math


class PotentialFields:
    def __init__(self):
        self.charge_laser_particle = 0.3
        self.charge_forward_boost = 20.0
        self.boost_distance = 0.5
        self.p_speed = 0.004
	self.min_power = 0.1
        self.stuck_power = 0.125
        self.p_steering = 1.33

	self.stuck_start_time = None

        rospy.Subscriber("/scan", numpy_msg(LaserScan), self.scan_callback)

        self.pub_goal = rospy.Publisher("~potentialFieldGoal", PointStamped, queue_size=1)
        self.pub_nav = rospy.Publisher("/drive", DriveCommand, queue_size=0)

    def scan_callback(self, msg):
        # Create potential gradients for all laser scan particles
        scan_rad_angles = ( (msg.angle_increment * np.arange(1081, dtype=float)) + msg.angle_min )

        scan_x_unit_vectors = -np.cos(scan_rad_angles)
        scan_y_unit_vectors = -np.sin(scan_rad_angles)

        scan_x_components = (self.charge_laser_particle * scan_x_unit_vectors) / np.power(msg.ranges, 1.8)
        scan_y_components = (self.charge_laser_particle * scan_y_unit_vectors) / np.power(msg.ranges, 1.8)

        # Add the potential for the point behind the robot (to give it a kick)
        kick_x_component = np.ones(1) * self.charge_forward_boost / self.boost_distance**2.0
        kick_y_component = np.zeros(1)

        # Add together the gradients to create a global gradient showing the robot which direction to travel in
        total_x_component = np.sum(scan_x_components) + kick_x_component
        total_y_component = np.sum(scan_y_components) + kick_y_component

        # Transform this gradient vector into a PoseStamped object
        visualizer_msg = PointStamped()
        visualizer_msg.header.frame_id = 'base_link'
        visualizer_msg.point.x = total_x_component
        visualizer_msg.point.y = total_y_component

        # Publish this goal so that we can see it in RVIZ
        self.pub_goal.publish(visualizer_msg)

        # Now, create a steering command to send to the vesc.
        command_msg = DriveCommand()
        command_msg.steering = (self.p_steering * np.sign(total_x_component) * math.atan2(total_y_component, total_x_component))
        
        command_msg.power = (self.p_speed * np.sign(total_x_component) * math.sqrt(total_x_component**2 + total_y_component**2))

        if abs(command_msg.power) < self.stuck_power:
            # start recovery after 3 seconds
            if self.stuck_start_time is None:
                self.stuck_start_time = rospy.get_time()
            elif rospy.get_time() - self.stuck_start_time > 3.0:
	    	rospy.logwarn("starting recovery!")
        	self.charge_forward_boost = -2.0

        # recover for 2 seconds
        if self.stuck_start_time is not None and rospy.get_time() - self.stuck_start_time > 5.0:
            rospy.loginfo("finished recovery!")
            self.stuck_start_time = None
            self.charge_forward_boost = 20.0

	rospy.loginfo("power: {}".format(command_msg.power))

	if abs(command_msg.power) < self.min_power:
            # set minimum power
	    if command_msg.power >= 0:
                command_msg.power = self.min_power
	    else:
	    	command_msg.power = -self.min_power

        # Publish the command
	command_msg.header.stamp = rospy.Time.now()
        self.pub_nav.publish(command_msg)



if __name__ == "__main__":
    rospy.init_node("potential_fields_node")
    pf = PotentialFields()
    rospy.spin()
