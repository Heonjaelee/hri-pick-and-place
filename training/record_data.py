#!/usr/bin/env python3
"""
record_data.py
제스처 확정 모델 학습용 데이터 수집

방식: 시스템을 켜놓고(규칙 모드) 작업자가 제스처를 시연하는 동안
      이 스크립트가 /quest/gesture, /gaze/target_3d 를 실시간 기록.
      터미널에서 숫자 키로 "지금 의도한 제스처"를 라벨링.

키 입력:
  0 : NONE (전환 중 / 의도 없음)
  1 : Open_Palm    2 : Pointing_Up   3 : Closed_Fist
  4 : Victory      5 : Pinch         6 : Thumb_Down
  s : 지금까지 데이터 저장 후 종료

출력: training/data/session_<시각>.npz
  gestures (N, 7), gazes (N, 4), labels (N,)

사용법: ros2 시스템 실행 상태에서
  python3 record_data.py
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
from std_msgs.msg import String, Float32, Bool
import numpy as np
import sys, os, termios, tty, select, time, threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', 'src', 'hri_perception'))
from hri_perception.model import encode_gesture_frame, encode_gaze_frame


class Recorder(Node):
    def __init__(self):
        super().__init__('data_recorder')
        self.gesture, self.conf = 'Open_Palm', 0.0
        self.gaze, self.fix = None, False
        self.label = 0
        self.rows_g, self.rows_z, self.rows_y = [], [], []

        self.create_subscription(String, '/quest/gesture',
                                 lambda m: setattr(self, 'gesture', m.data), 10)
        self.create_subscription(Float32, '/quest/gesture_confidence',
                                 lambda m: setattr(self, 'conf', m.data), 10)
        self.create_subscription(PointStamped, '/gaze/target_3d',
                                 self.z_cb, 10)
        self.create_subscription(Bool, '/gaze/fixation',
                                 lambda m: setattr(self, 'fix', m.data), 10)
        self.create_timer(1 / 30, self.tick)   # 30Hz 기록

    def z_cb(self, m):
        self.gaze = (m.point.x, m.point.y, m.point.z)

    def tick(self):
        if self.gaze is None:
            return
        self.rows_g.append(encode_gesture_frame(self.gesture, self.conf))
        self.rows_z.append(encode_gaze_frame(*self.gaze, self.fix))
        self.rows_y.append(self.label)

    def save(self):
        os.makedirs(os.path.join(os.path.dirname(__file__), 'data'),
                    exist_ok=True)
        path = os.path.join(os.path.dirname(__file__), 'data',
                            f'session_{int(time.time())}.npz')
        np.savez(path,
                 gestures=np.array(self.rows_g, dtype=np.float32),
                 gazes=np.array(self.rows_z, dtype=np.float32),
                 labels=np.array(self.rows_y, dtype=np.int64))
        print(f'\n저장: {path} ({len(self.rows_y)} 프레임)')


def key_loop(node):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    names = ['NONE', 'Open_Palm', 'Pointing_Up', 'Closed_Fist',
             'Victory', 'Pinch', 'Thumb_Down']
    try:
        tty.setcbreak(fd)
        print('라벨 키: 0=NONE 1=Palm 2=Point 3=Fist 4=Victory 5=Pinch 6=ThumbDown / s=저장종료')
        while rclpy.ok():
            if select.select([sys.stdin], [], [], 0.1)[0]:
                c = sys.stdin.read(1)
                if c in '0123456':
                    node.label = int(c)
                    print(f'\r현재 라벨: {names[node.label]}        ',
                          end='', flush=True)
                elif c == 's':
                    node.save()
                    rclpy.shutdown()
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main():
    rclpy.init()
    node = Recorder()
    threading.Thread(target=key_loop, args=(node,), daemon=True).start()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
