#!/usr/bin/env python3
"""
stream_node.py
/camera/left/image_raw 를 JPEG 압축해서 Quest Pro(VideoReceiver.cs)로
WebSocket 전송 (30fps)
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import asyncio
import websockets
import threading


class StreamNode(Node):
    def __init__(self):
        super().__init__('stream_node')

        self.declare_parameter('port', 8765)
        self.declare_parameter('jpeg_quality', 80)
        self.port    = self.get_parameter('port').value
        self.quality = self.get_parameter('jpeg_quality').value

        self.bridge = CvBridge()
        self.latest = None
        self.lock   = threading.Lock()

        self.create_subscription(Image, '/camera/left/image_raw',
                                 self.image_cb, 5)
        threading.Thread(target=self._run_ws, daemon=True).start()
        self.get_logger().info(f'stream_node 시작 (port {self.port})')

    def image_cb(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        ok, jpg = cv2.imencode('.jpg', frame,
                               [cv2.IMWRITE_JPEG_QUALITY, self.quality])
        if ok:
            with self.lock:
                self.latest = jpg.tobytes()

    def _run_ws(self):
        asyncio.run(self._server())

    async def _server(self):
        async with websockets.serve(self._handle, '0.0.0.0', self.port,
                                    max_size=2**22):
            await asyncio.Future()

    async def _handle(self, ws):
        self.get_logger().info('영상 스트림 클라이언트 연결됨')
        try:
            while True:
                with self.lock:
                    data = self.latest
                if data:
                    await ws.send(data)
                await asyncio.sleep(1 / 30)
        except websockets.ConnectionClosed:
            self.get_logger().warn('영상 스트림 연결 끊김')


def main():
    rclpy.init()
    node = StreamNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
