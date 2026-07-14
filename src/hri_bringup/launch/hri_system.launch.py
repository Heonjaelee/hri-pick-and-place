from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package='hri_camera',     executable='camera_node',
             output='screen'),
        Node(package='hri_quest',      executable='quest_bridge_node',
             output='screen'),
        Node(package='hri_quest',      executable='stream_node',
             output='screen'),
        Node(package='hri_perception', executable='gaze_to_3d_node',
             output='screen'),
        Node(package='hri_perception', executable='intent_node',
             output='screen'),
        Node(package='hri_control',    executable='piper_controller_node',
             output='screen',
             parameters=[{'can_port': 'can0'}]),
    ])
