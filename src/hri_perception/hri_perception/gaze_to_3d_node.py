#!/usr/bin/env python3
"""
gaze_to_3d_node.py
화면 정규화 gaze 좌표 -> 카메라 픽셀 -> 뎁스 -> 로봇 base 좌표계 3D 점

구독: /quest/gaze (Point, x/y = 0~1)
      /camera/depth (Image, 32FC1, 미터)
발행: /gaze/target_3d (PointStamped, 로봇 base 좌표계)
      /gaze/fixation  (Bool, 시선 고정 여부)

config/cam_to_robot.npy : calibrate_cam_to_robot.py 로 만든 4x4 변환행렬
config/stereo_params.npz : 카메라 내부 파라미터 (없으면 기본값)
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Point, PointStamped
from std_msgs.msg import Bool
from cv_bridge import CvBridge
import numpy as np
import os
from collections import deque

PARAM_PATH = os.path.expanduser('~/hri_robot_ws/config/stereo_params.npz')
EXTRINSIC_PATH = os.path.expanduser('~/hri_robot_ws/config/cam_to_robot.npy')


class GazeTo3DNode(Node):
    def __init__(self):
        super().__init__('gaze_to_3d_node')
        self.bridge = CvBridge()
        self.depth = None

        # 카메라 내부 파라미터
        if os.path.exists(PARAM_PATH):
            p = np.load(PARAM_PATH)
            P1 = p['P1']
            self.fx, self.fy = P1[0, 0], P1[1, 1]
            self.cx, self.cy = P1[0, 2], P1[1, 2]
        else:
            self.fx = self.fy = 1024.0
            self.cx, self.cy = 640.0, 360.0
            self.get_logger().warn('stereo_params.npz 없음 - 기본 내부 파라미터 사용')

        # 카메라 -> 로봇 외부 파라미터
        if os.path.exists(EXTRINSIC_PATH):
            self.T_cr = np.load(EXTRINSIC_PATH)
            self.get_logger().info('카메라-로봇 캘리브레이션 로드 완료')
        else:
            self.T_cr = np.eye(4)
            self.get_logger().warn(
                'cam_to_robot.npy 없음 - 항등 변환 사용 (calibrate_cam_to_robot.py 실행 필요)')

        # 시선 안정화 버퍼 (10프레임, 3cm 이내면 fixation)
        self.buf = deque(maxlen=10)
        self.fixation_tol = 0.03

        self.create_subscription(Image, '/camera/depth', self.depth_cb, 5)
        self.create_subscription(Point, '/quest/gaze',   self.gaze_cb, 10)
        self.pub_target = self.create_publisher(PointStamped, '/gaze/target_3d', 10)
        self.pub_fix    = self.create_publisher(Bool, '/gaze/fixation', 10)
        self.get_logger().info('gaze_to_3d_node 시작')

    def depth_cb(self, msg):
        self.depth = self.bridge.imgmsg_to_cv2(msg, '32FC1')

    def gaze_cb(self, msg):
        if self.depth is None:
            return

        h, w = self.depth.shape
        u = int(np.clip(msg.x * w, 0, w - 1))
        v = int(np.clip(msg.y * h, 0, h - 1))

        # 주변 7x7 영역의 유효 뎁스 중앙값 (구멍/노이즈 대응)
        u0, u1 = max(0, u - 3), min(w, u + 4)
        v0, v1 = max(0, v - 3), min(h, v + 4)
        patch = self.depth[v0:v1, u0:u1]
        valid = patch[patch > 0]
        if valid.size < 5:
            return
        z = float(np.median(valid))
        if not (0.15 < z < 2.0):
            return

        # 픽셀 -> 카메라 좌표
        x = (u - self.cx) * z / self.fx
        y = (v - self.cy) * z / self.fy
        p_cam = np.array([x, y, z, 1.0])

        # 카메라 -> 로봇 좌표
        p_rob = self.T_cr @ p_cam

        # fixation 판정
        self.buf.append(p_rob[:3])
        is_fix = False
        if len(self.buf) == self.buf.maxlen:
            pts = np.array(self.buf)
            is_fix = bool(np.all(pts.std(axis=0) < self.fixation_tol))
            if is_fix:
                p_out = pts.mean(axis=0)   # fixation 중엔 평균값으로 안정화
            else:
                p_out = p_rob[:3]
        else:
            p_out = p_rob[:3]

        out = PointStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = 'base_link'
        out.point.x, out.point.y, out.point.z = map(float, p_out)
        self.pub_target.publish(out)

        f = Bool()
        f.data = is_fix
        self.pub_fix.publish(f)


def main():
    rclpy.init()
    node = GazeTo3DNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
