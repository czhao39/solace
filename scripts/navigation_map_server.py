#!/usr/bin/env python

import subprocess

import rospy
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import Bool

STITCHING_PATH = "./image-stitching"
MAP_DIR_PATH = "../maps/"


class NavigationMapServer:
    """
    This node publishes altered maps used for navigation.
    """

    def __init__(self):
        self.map_pub = rospy.Publisher("navigation_map", OccupancyGrid, queue_size=0, latch=True)
        self.gmapping_disk_map_pub = rospy.Publisher("gmapping_disk_map", OccupancyGrid, queue_size=0)
        self.map_sub = rospy.Subscriber("map", OccupancyGrid, self.map_cb)
        self.lost_sub = rospy.Subscriber("is_lost", Bool, self.lost_cb)

        self.is_lost = False
        self.map_msg = OccupancyGrid()
        self.lost_count = 0

    def map_cb(self, msg):
        if self.is_lost:
            self.lost_count += 1
            if self.lost_count % 3 == 0:  # update map on disk every 3 updates
                self.gmapping_disk_map_pub.publish(self.map_msg)  # save gmapping map to disk
                # stitch gmapping map to full map
                try:
                    subprocess.check_call([STITCHING_PATH, "{}full_map.pgm".format(MAP_DIR_PATH),
                                           "{}gmapping_map.pgm".format(MAP_DIR_PATH)], stderr=subprocess.STDOUT)
                    subprocess.call(["convert", "-compress", "none", "out.jpg", "{}full_map.pgm".format(MAP_DIR_PATH)])
                except subprocess.CalledProcessError:
                    print "failed to stitch!"
                    # TODO: update map_msg map and metadata
        else:
            self.map_msg = msg
        actual_map = self.map_msg.data

        # Set all unknown space as open
        self.map_msg.data = [cell if cell != -1 else 0 for cell in self.map_msg.data]
        self.map_pub.publish(self.map_msg)

        # Revert to actual map
        self.map_msg.data = actual_map

    def lost_cb(self, msg):
        self.is_lost = msg.data

    @staticmethod
    def file_to_occupancygrid(file_name, grid_msg):
        with open(file_name, "r") as infile:
            infile.next()
            grid_msg.info.width, grid_msg.info.height = map(int, infile.next().split())
            max_intensity = int(infile.next())
            mult = 100.0 / max_intensity
            grid_msg.data = [int(p) * mult for p in infile.read().split()]


if __name__ == "__main__":
    rospy.init_node("navigation_map_server")
    server = NavigationMapServer()
    rospy.spin()
