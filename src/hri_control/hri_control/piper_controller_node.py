#!/usr/bin/env python3
"""
piper_controller_node.py
/intent/command 를 받아 AgileX Piper 로봇팔 + 그리퍼를 제어

의존성: piper_sdk (pip install piper_sdk)
        CAN 연결: sudo ip link set can0 up type can bitrate 1000000

동작 시퀀스:
  MOVE_TO : end-effector를 목표 위치로 이동 (그리퍼 상태 유지)
  PICK    : 목표 8cm 위 접근 -> 하강 -> 그리퍼 닫기 -> 10cm 들어올림
  PLACE   : 목표 10cm 위 접근 -> 하강 -> 그리퍼 열기 -> 10cm 상승
  HOME    : 홈 자세 복귀 + 그리퍼 열기
  ABORT   : 진행 중 시퀀스 즉시 중단 (그리퍼는 유지 - 물체 낙하 방지)

piper_sdk가 없으면 시뮬레이션 모드로 동작 (로그만 출력)
"""
import rclpy
from rclpy.node import Node
from hri_msgs.msg import RobotIntent
from std_msgs.msg import String
import numpy as np
import threading
import time

# 동작 코드
IDLE, MOVE_TO, PICK, PLACE, HOME, ABORT = range(6)

# ── 로봇 설정 ──
HOME_POS_M      = np.array([0.20, 0.0, 0.30])   # 홈 위치 (base 기준, m)
GRIP_DOWN_RPY   = np.array([0.0, 85.0, 0.0])    # 그리퍼 아래향 자세 (deg)
APPROACH_OFFSET = 0.08    # 파지 접근 높이 (m)
LIFT_OFFSET     = 0.10    # 파지 후 들어올림 (m)
GRIPPER_OPEN    = 70000   # 0.001mm 단위 (70mm 개방)
GRIPPER_CLOSE   = 0
GRIPPER_EFFORT  = 1000    # 0.001 N/m
MOVE_SPEED      = 30      # 0~100 %
SETTLE_TIME     = 1.5     # 각 모션 스텝 대기 (초) - 연구용 단순 구현


class PiperControllerNode(Node):
    def __init__(self):
        super().__init__('piper_controller_node')

        self.declare_parameter('can_port', 'can0')
        can_port = self.get_parameter('can_port').value

        # piper_sdk 연결 (없으면 시뮬레이션 모드)
        self.piper = None
        try:
            from piper_sdk import C_PiperInterface_V2
            self.piper = C_PiperInterface_V2(can_port)
            self.piper.ConnectPort()
            time.sleep(0.5)
            while not self.piper.EnablePiper():
                time.sleep(0.01)
            self.get_logger().info(f'Piper 연결 완료 ({can_port})')
        except Exception as e:
            self.get_logger().warn(f'piper_sdk 사용 불가 - 시뮬레이션 모드: {e}')

        self.busy       = False        # 시퀀스 실행 중
        self.abort_flag = threading.Event()
        self.holding    = False        # 물체 파지 중 여부
        self.last_cmd_t = 0.0

        self.create_subscription(RobotIntent, '/intent/command',
                                 self.intent_cb, 10)
        self.pub_state = self.create_publisher(String, '/robot/state', 10)
        self.get_logger().info('piper_controller_node 시작')

        # 시작 시 홈 + 그리퍼 열기
        threading.Thread(target=self.seq_home, daemon=True).start()

    # ────────────────────────────── intent 처리
    def intent_cb(self, msg):
        action = msg.action

        # ABORT는 언제나 즉시
        if action == ABORT:
            self.abort_flag.set()
            self.stop_motion()
            self.publish_state('ABORTED')
            return

        if self.busy or action == IDLE:
            return

        # 같은 명령 연타 방지 (1초 디바운스)
        now = time.time()
        if now - self.last_cmd_t < 1.0:
            return
        self.last_cmd_t = now

        target = np.array([msg.target_position.x,
                           msg.target_position.y,
                           msg.target_position.z])

        if action == MOVE_TO:
            threading.Thread(target=self.seq_move, args=(target,),
                             daemon=True).start()
        elif action == PICK:
            if self.holding:
                # 이미 파지 중이면 Closed_Fist = 들고 이동
                threading.Thread(target=self.seq_move, args=(target,),
                                 daemon=True).start()
            else:
                threading.Thread(target=self.seq_pick, args=(target,),
                                 daemon=True).start()
        elif action == PLACE:
            threading.Thread(target=self.seq_place, args=(target,),
                             daemon=True).start()
        elif action == HOME:
            threading.Thread(target=self.seq_home, daemon=True).start()

    # ────────────────────────────── 모션 시퀀스
    def seq_move(self, target):
        self.begin('MOVE_TO')
        self.goto(target)
        self.end()

    def seq_pick(self, target):
        self.begin('PICK')
        approach = target + [0, 0, APPROACH_OFFSET]
        ok = (self.goto(approach)
              and self.goto(target)
              and self.gripper(GRIPPER_CLOSE)
              and self.goto(target + [0, 0, LIFT_OFFSET]))
        if ok:
            self.holding = True
        self.end()

    def seq_place(self, target):
        self.begin('PLACE')
        above = target + [0, 0, LIFT_OFFSET]
        ok = (self.goto(above)
              and self.goto(target + [0, 0, 0.02])
              and self.gripper(GRIPPER_OPEN)
              and self.goto(above))
        if ok:
            self.holding = False
        self.end()

    def seq_home(self):
        self.begin('HOME')
        self.goto(HOME_POS_M)
        if not self.holding:
            self.gripper(GRIPPER_OPEN)
        self.end()

    def begin(self, name):
        self.busy = True
        self.abort_flag.clear()
        self.publish_state(name)

    def end(self):
        self.busy = False
        self.publish_state('DONE' if not self.abort_flag.is_set()
                           else 'ABORTED')

    # ────────────────────────────── 저수준 명령
    def goto(self, pos_m) -> bool:
        """end-effector를 pos_m(미터)로 이동. abort 시 False"""
        if self.abort_flag.is_set():
            return False

        x, y, z = (np.asarray(pos_m) * 1e6).astype(int)   # m -> 0.001mm
        rx, ry, rz = (GRIP_DOWN_RPY * 1000).astype(int)   # deg -> 0.001deg

        if self.piper:
            self.piper.MotionCtrl_2(0x01, 0x00, MOVE_SPEED, 0x00)
            self.piper.EndPoseCtrl(int(x), int(y), int(z),
                                   int(rx), int(ry), int(rz))
        else:
            self.get_logger().info(f'[SIM] goto {np.round(pos_m, 3)}')

        # 단순 시간 대기 방식 (연구용). abort 체크하며 대기
        t0 = time.time()
        while time.time() - t0 < SETTLE_TIME:
            if self.abort_flag.is_set():
                return False
            time.sleep(0.05)
        return True

    def gripper(self, opening) -> bool:
        if self.abort_flag.is_set():
            return False
        if self.piper:
            self.piper.GripperCtrl(abs(int(opening)), GRIPPER_EFFORT,
                                   0x01, 0)
        else:
            state = '열기' if opening > 0 else '닫기'
            self.get_logger().info(f'[SIM] 그리퍼 {state}')
        time.sleep(1.0)
        return True

    def stop_motion(self):
        if self.piper:
            # 0x01 = 급정지
            self.piper.MotionCtrl_1(0x01, 0, 0)
            time.sleep(0.1)
            self.piper.MotionCtrl_1(0x02, 0, 0)   # 정지 해제(재개 가능 상태)
        self.get_logger().warn('모션 정지')

    def publish_state(self, s):
        msg = String()
        msg.data = s
        self.pub_state.publish(msg)


def main():
    rclpy.init()
    node = PiperControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
