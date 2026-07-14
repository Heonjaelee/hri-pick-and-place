#!/usr/bin/env python3
"""
intent_node.py
제스처(WHAT) + gaze(WHERE) -> 로봇 명령

두 가지 동작 모드:
  1. 규칙 모드 (기본) : 제스처 유지시간 + gaze fixation으로 확정
     -> 모델 학습 전에도 전체 시스템이 바로 동작
  2. 모델 모드 : config/gesture_confirm.pt 가 있으면 자동으로
     GRU+Cross-Attention 모델로 제스처 확정 (규칙보다 빠르고 부드러움)

제스처 -> 동작 매핑 (확정안):
  Open_Palm    -> IDLE   (대기, gaze 무시)
  Pointing_Up  -> MOVE_TO (gaze 위치로 이동)
  Closed_Fist  -> PICK    (gaze 위치 파지 / 파지 중이면 들고 이동)
  Victory      -> PLACE   (gaze 위치에 내려놓기)
  Pinch        -> HOME    (홈 복귀, gaze 무시)
  Thumb_Down   -> ABORT   (즉시 정지, 규칙으로 항상 처리 - 안전)

발행: /intent/command (hri_msgs/RobotIntent)
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
from std_msgs.msg import String, Float32, Bool
from hri_msgs.msg import RobotIntent
import numpy as np
import time
import os
from collections import deque

from hri_perception.model import (
    GestureConfirmModel, CLASSES, encode_gesture_frame, encode_gaze_frame,
    SEQ_LEN)

MODEL_PATH = os.path.expanduser('~/hri_robot_ws/config/gesture_confirm.pt')

ACTION = {'IDLE': 0, 'MOVE_TO': 1, 'PICK': 2, 'PLACE': 3,
          'HOME': 4, 'ABORT': 5}

GESTURE_TO_ACTION = {
    'Open_Palm':   'IDLE',
    'Pointing_Up': 'MOVE_TO',
    'Closed_Fist': 'PICK',
    'Victory':     'PLACE',
    'Pinch':       'HOME',
    'Thumb_Down':  'ABORT',
}

# gaze 위치가 필요한 동작
NEEDS_GAZE = {'MOVE_TO', 'PICK', 'PLACE'}

# 작업 공간 한계 (로봇 base 기준, 미터) - 안전 필터
WS_MIN = np.array([-0.1, -0.5, -0.05])
WS_MAX = np.array([ 0.7,  0.5,  0.6])


class IntentNode(Node):
    def __init__(self):
        super().__init__('intent_node')

        # 최신 입력 상태
        self.gesture    = 'Open_Palm'
        self.conf       = 0.0
        self.gaze       = None      # np.array(3,)
        self.fixation   = False

        # 규칙 모드용 타이머
        self.g_hold_start = time.time()
        self.g_prev       = 'Open_Palm'

        # 모델 모드용 시퀀스 버퍼
        self.g_buf = deque(maxlen=SEQ_LEN)
        self.z_buf = deque(maxlen=SEQ_LEN)

        # 모델 로드 시도
        self.model = None
        if os.path.exists(MODEL_PATH):
            try:
                import torch
                self.torch = torch
                self.model = GestureConfirmModel()
                self.model.load_state_dict(
                    torch.load(MODEL_PATH, map_location='cpu'))
                self.model.eval()
                self.get_logger().info('모델 모드: gesture_confirm.pt 로드 완료')
            except Exception as e:
                self.get_logger().warn(f'모델 로드 실패, 규칙 모드로 동작: {e}')
                self.model = None
        else:
            self.get_logger().info('규칙 모드로 동작 (모델 파일 없음)')

        self.create_subscription(String, '/quest/gesture', self.g_cb, 10)
        self.create_subscription(Float32, '/quest/gesture_confidence',
                                 self.c_cb, 10)
        self.create_subscription(PointStamped, '/gaze/target_3d',
                                 self.z_cb, 10)
        self.create_subscription(Bool, '/gaze/fixation', self.f_cb, 10)

        self.pub = self.create_publisher(RobotIntent, '/intent/command', 10)
        self.create_timer(1 / 20, self.tick)   # 20Hz
        self.get_logger().info('intent_node 시작')

    # ── 콜백들 ──
    def g_cb(self, msg):
        self.gesture = msg.data

    def c_cb(self, msg):
        self.conf = msg.data

    def z_cb(self, msg):
        self.gaze = np.array([msg.point.x, msg.point.y, msg.point.z])

    def f_cb(self, msg):
        self.fixation = msg.data

    # ── 메인 루프 ──
    def tick(self):
        # 버퍼 갱신 (모델 모드용)
        self.g_buf.append(encode_gesture_frame(self.gesture, self.conf))
        if self.gaze is not None:
            self.z_buf.append(encode_gaze_frame(
                *self.gaze, self.fixation))

        # 1) ABORT는 항상 규칙으로 즉시 처리 (안전 최우선)
        if self.gesture == 'Thumb_Down' and self.conf > 0.6:
            self.publish('ABORT', None, 1.0)
            return

        # 2) 제스처 확정
        if self.model is not None and len(self.g_buf) == SEQ_LEN \
                and len(self.z_buf) == SEQ_LEN:
            confirmed, c = self.confirm_by_model()
        else:
            confirmed, c = self.confirm_by_rule()

        if confirmed is None or confirmed == 'NONE':
            return

        action = GESTURE_TO_ACTION[confirmed]

        # 3) gaze 필요한 동작은 fixation + 작업공간 검사
        target = None
        if action in NEEDS_GAZE:
            if self.gaze is None or not self.fixation:
                return
            if np.any(self.gaze < WS_MIN) or np.any(self.gaze > WS_MAX):
                self.get_logger().warn(
                    f'목표가 작업 공간 밖: {self.gaze.round(3)}', throttle_duration_sec=2.0)
                return
            target = self.gaze

        self.publish(action, target, c)

    # ── 확정 로직 ──
    def confirm_by_rule(self, hold=0.5, min_conf=0.75):
        """같은 제스처를 0.5초 이상 유지 + 신뢰도 0.75 이상"""
        if self.gesture != self.g_prev:
            self.g_prev = self.gesture
            self.g_hold_start = time.time()
            return None, 0.0
        if self.conf < min_conf:
            return None, 0.0
        if time.time() - self.g_hold_start >= hold:
            return self.gesture, self.conf
        return None, 0.0

    def confirm_by_model(self, min_conf=0.70):
        g = self.torch.tensor([list(self.g_buf)],
                              dtype=self.torch.float32)
        z = self.torch.tensor([list(self.z_buf)],
                              dtype=self.torch.float32)
        with self.torch.no_grad():
            logits = self.model(g, z)
            probs = self.torch.softmax(logits, dim=-1)[0]
            idx = int(probs.argmax())
            c = float(probs[idx])
        if c < min_conf:
            return None, 0.0
        return CLASSES[idx], c

    # ── 발행 ──
    def publish(self, action: str, target, conf: float):
        out = RobotIntent()
        out.header.stamp = self.get_clock().now().to_msg()
        out.action = ACTION[action]
        out.confidence = float(conf)
        out.gesture_label = self.gesture
        if target is not None:
            out.target_position.x = float(target[0])
            out.target_position.y = float(target[1])
            out.target_position.z = float(target[2])
        self.pub.publish(out)


def main():
    rclpy.init()
    node = IntentNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
