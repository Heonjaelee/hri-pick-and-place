#!/usr/bin/env python3
"""
camera_node.py
oCamS-1CGN-U 스테레오 카메라에서 Left RGB + 뎁스맵을 발행

발행 토픽:
  /camera/left/image_raw  (sensor_msgs/Image, bgr8)
  /camera/depth           (sensor_msgs/Image, 32FC1, 미터 단위)

calibration/calibrate_stereo.py 로 만든 config/stereo_params.npz 가 있으면
정밀 렉티피케이션을 적용하고, 없으면 기본 파라미터로 동작 (정확도 낮음)
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np
import os

# oCamS-1CGN-U 기본 스펙 (캘리브레이션 전 임시값)
DEFAULT_FOCAL_PX = 1024.0   # 1280px, FOV 65도 기준 추정
BASELINE_M       = 0.120    # 120mm

PARAM_PATH = os.path.expanduser('~/hri_robot_ws/config/stereo_params.npz')


class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        self.bridge = CvBridge()

        self.declare_parameter('device_id', 0)
        self.declare_parameter('fps', 30)
        dev = self.get_parameter('device_id').value
        fps = self.get_parameter('fps').value

        self.pub_left  = self.create_publisher(Image, '/camera/left/image_raw', 5)
        self.pub_depth = self.create_publisher(Image, '/camera/depth', 5)

        # oCamS: 좌우가 한 프레임에 합쳐진 2560x720 출력
        self.cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  2560)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,  720)
        self.cap.set(cv2.CAP_PROP_FPS,           fps)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
        if not self.cap.isOpened():
            self.get_logger().error('카메라를 열 수 없습니다. device_id 확인')

        # 캘리브레이션 파라미터 로드 (있으면)
        self.rectify = None
        self.f = DEFAULT_FOCAL_PX
        self.B = BASELINE_M
        if os.path.exists(PARAM_PATH):
            p = np.load(PARAM_PATH)
            size = (1280, 720)
            m1l, m2l = cv2.initUndistortRectifyMap(
                p['K1'], p['D1'], p['R1'], p['P1'], size, cv2.CV_32FC1)
            m1r, m2r = cv2.initUndistortRectifyMap(
                p['K2'], p['D2'], p['R2'], p['P2'], size, cv2.CV_32FC1)
            self.rectify = (m1l, m2l, m1r, m2r)
            self.f = float(p['P1'][0, 0])
            self.B = float(abs(p['T'][0]))
            self.get_logger().info(
                f'캘리브레이션 적용: f={self.f:.1f}px B={self.B*1000:.1f}mm')
        else:
            self.get_logger().warn(
                '캘리브레이션 파일 없음 - 기본 파라미터 사용 (calibrate_stereo.py 실행 권장)')

        self.stereo = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=128,        # 120mm 베이스라인, 근거리 작업용
            blockSize=9,
            P1=8 * 9 * 9,
            P2=32 * 9 * 9,
            disp12MaxDiff=1,
            uniquenessRatio=10,
            speckleWindowSize=100,
            speckleRange=32,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
        )

        self.create_timer(1.0 / fps, self.timer_cb)
        self.get_logger().info('camera_node 시작')

    def timer_cb(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        left  = frame[:, :1280]
        right = frame[:, 1280:]

        if self.rectify is not None:
            m1l, m2l, m1r, m2r = self.rectify
            left  = cv2.remap(left,  m1l, m2l, cv2.INTER_LINEAR)
            right = cv2.remap(right, m1r, m2r, cv2.INTER_LINEAR)

        # 뎁스 계산 (절반 해상도로 속도 확보 후 업스케일)
        lg = cv2.cvtColor(cv2.resize(left,  (640, 360)), cv2.COLOR_BGR2GRAY)
        rg = cv2.cvtColor(cv2.resize(right, (640, 360)), cv2.COLOR_BGR2GRAY)
        disp = self.stereo.compute(lg, rg).astype(np.float32) / 16.0
        disp = cv2.resize(disp, (1280, 720)) * 2.0   # 해상도 보정

        with np.errstate(divide='ignore'):
            depth = (self.f * self.B) / disp
        depth[(disp <= 0) | (depth > 3.0) | (depth < 0.1)] = 0.0

        now = self.get_clock().now().to_msg()

        msg_l = self.bridge.cv2_to_imgmsg(left, 'bgr8')
        msg_l.header.stamp = now
        msg_l.header.frame_id = 'camera_left'
        self.pub_left.publish(msg_l)

        msg_d = self.bridge.cv2_to_imgmsg(depth.astype(np.float32), '32FC1')
        msg_d.header.stamp = now
        msg_d.header.frame_id = 'camera_left'
        self.pub_depth.publish(msg_d)


def main():
    rclpy.init()
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cap.release()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
