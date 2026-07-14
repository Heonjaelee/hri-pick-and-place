#!/usr/bin/env python3
"""
quest_bridge_node.py
Quest Pro(Unity QuestSender.cs)가 보내는 gaze + 제스처를 WebSocket으로 수신해서
ROS2 토픽으로 발행

발행 토픽:
  /quest/gaze                (geometry_msgs/Point)  x,y = 화면 정규화 좌표 0~1
  /quest/gesture             (std_msgs/String)
  /quest/gesture_confidence  (std_msgs/Float32)
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
from std_msgs.msg import String, Float32
import asyncio
import websockets
import json
import threading


class QuestBridgeNode(Node):
    def __init__(self):
        super().__init__('quest_bridge_node')

        self.declare_parameter('port', 8766)
        self.port = self.get_parameter('port').value

        self.pub_gaze    = self.create_publisher(Point,   '/quest/gaze', 10)
        self.pub_gesture = self.create_publisher(String,  '/quest/gesture', 10)
        self.pub_conf    = self.create_publisher(Float32, '/quest/gesture_confidence', 10)

        threading.Thread(target=self._run_ws, daemon=True).start()
        self.get_logger().info(f'quest_bridge_node 시작 (port {self.port})')

    def _run_ws(self):
        asyncio.run(self._server())

    async def _server(self):
        async with websockets.serve(self._handle, '0.0.0.0', self.port,
                                    max_size=2**16):
            await asyncio.Future()

    async def _handle(self, ws):
        self.get_logger().info('Quest Pro 연결됨')
        try:
            async for raw in ws:
                try:
                    d = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                g = Point()
                g.x = float(d.get('gaze_x', 0.5))
                g.y = float(d.get('gaze_y', 0.5))
                self.pub_gaze.publish(g)

                s = String()
                s.data = str(d.get('gesture', 'Open_Palm'))
                self.pub_gesture.publish(s)

                c = Float32()
                c.data = float(d.get('confidence', 0.0))
                self.pub_conf.publish(c)
        except websockets.ConnectionClosed:
            self.get_logger().warn('Quest Pro 연결 끊김')


def main():
    rclpy.init()
    node = QuestBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
