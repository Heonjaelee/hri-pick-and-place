# HRI Pick & Place 시스템

> 2026학년도 UGRP 연구과제 · 사용자 상호작용형 멀티모달 로봇 디스플레이 제어 시스템

MetaQuest Pro의 시선(gaze)과 손 제스처로 Piper 로봇팔(그리퍼 장착)을 제어해
pick and place를 수행하는 연구 프로젝트.

- **Gaze = WHERE**: 스테레오 카메라(oCamS-1CGN-U)가 찍는 작업 환경 영상을
  Quest Pro 화면에 띄우고, 작업자가 화면에서 바라보는 지점을 로봇 좌표계
  3D 위치로 변환
- **Gesture = WHAT**: Quest Pro 손 트래킹에서 분류한 6개 제스처가 로봇 동작 결정

소프트웨어는 로봇팔 없이도 **시뮬레이션 모드**로 전체 흐름을 검증할 수 있게
설계되어 있습니다 (`piper_controller_node`가 `piper_sdk` 미설치 시 자동으로
로그 출력 모드로 동작). 팀원 간 작업 방식은 [CONTRIBUTING.md](CONTRIBUTING.md) 참고.

## 제스처 매핑 (확정 X)

| 제스처 | 로봇 동작 | gaze 사용 |
|---|---|---|
| Open_Palm (편 손) | 대기 | 무시 |
| Pointing_Up (검지) | 이동 | 목표 위치 |
| Closed_Fist (주먹) | 파지 / 들고 이동 | 파지·이동 위치 |
| Victory (브이) | 내려놓기 | 내려놓을 위치 |
| Pinch (엄지+검지) | 홈 복귀 | 무시 |
| Thumb_Down (엄지 아래) | 즉시 정지 | 무시 |

## 디렉토리 구조

```
hri_robot_ws/
├── unity/            # Quest Pro Unity 스크립트 (3개)
├── calibration/      # 캘리브레이션 스크립트 (2개)
├── training/         # 데이터 수집 + 모델 학습
├── config/           # 캘리브레이션 결과 + 학습 모델 (생성됨)
└── src/              # ROS2 패키지 6개
    ├── hri_msgs        커스텀 메시지 (RobotIntent)
    ├── hri_camera      camera_node: RGB + 뎁스 발행
    ├── hri_quest       quest_bridge_node, stream_node
    ├── hri_perception  gaze_to_3d_node, intent_node (+ 모델)
    ├── hri_control     piper_controller_node (그리퍼 포함)
    └── hri_bringup     전체 launch
```

## 1. PC 환경 설정 (Ubuntu 22.04 + ROS2 Humble)

```bash
# ROS2 의존성
sudo apt install ros-humble-cv-bridge python3-colcon-common-extensions

# Python 의존성
pip install -r requirements.txt

# Piper CAN 연결 (USB-CAN 어댑터)
sudo ip link set can0 up type can bitrate 1000000

# 빌드
cd ~/hri_robot_ws
colcon build --symlink-install
source install/setup.bash
```

## 2. Unity (Quest Pro) 설정

1. Unity 2022 LTS + Meta XR All-in-One SDK 설치
2. 프로젝트 설정에서 Eye Tracking, Hand Tracking 권한 활성화
   (Quest Pro 기기에서도 시선 추적 허용 필요)
3. [NativeWebSocket](https://github.com/endel/NativeWebSocket) 패키지 추가
4. 씬 구성:
   - `OVRCameraRig` + `OVREyeGaze` 컴포넌트
   - 오른손에 `OVRHand` + `OVRSkeleton` + **GestureClassifier.cs**
   - 작업자 정면에 World Space Canvas + RawImage (videoScreen)
     + **VideoReceiver.cs**
   - 빈 오브젝트에 **QuestSender.cs** (eyeGaze, videoScreen, gesture 연결)
5. 두 스크립트의 `pcAddress`를 PC IP로 수정 후 Quest Pro에 빌드

## 3. 캘리브레이션 (최초 1회)

```bash
# (1) 스테레오 캘리브레이션 - 9x6 체커보드 필요
python3 calibration/calibrate_stereo.py --device 0 --square 0.025
# -> config/stereo_params.npz

# (2) 카메라-로봇 좌표 캘리브레이션
#     마커 클릭 -> 로봇 끝을 마커에 대고 엔터, 4~6개 점
python3 calibration/calibrate_cam_to_robot.py --device 0
# -> config/cam_to_robot.npy
```

`src/hri_perception/hri_perception/model.py` 와 `intent_node.py` 의
`WS_MIN/WS_MAX` (작업 공간 한계)를 실제 환경에 맞게 수정하세요.

## 4. 실행

```bash
source install/setup.bash
ros2 launch hri_bringup hri_system.launch.py
```

그 후 Quest Pro 앱 실행 → 화면에 카메라 영상이 보이면 연결 완료.

**규칙 모드로 즉시 동작합니다** (제스처 0.5초 유지 + 시선 고정으로 확정).
모델 학습 전에도 전체 파이프라인 검증 가능.

### 동작 확인용 명령

```bash
ros2 topic hz /camera/left/image_raw     # 30Hz 근처면 정상
ros2 topic echo /quest/gesture            # Quest 제스처 수신 확인
ros2 topic echo /gaze/target_3d           # 시선 3D 좌표 확인
ros2 topic echo /intent/command           # 최종 로봇 명령 확인
ros2 topic echo /robot/state              # 로봇 시퀀스 상태
```

## 5. 딥러닝 모델 학습 (선택 - 반응성 개선)

규칙 모드는 고정 지연(0.5초)이 있지만, GRU + Cross-Attention 모델은
제스처가 형성되는 패턴과 시선 안착을 함께 보고 더 빠르고 부드럽게 확정합니다.

```bash
# (1) 시스템 실행 상태에서 데이터 수집
#     제스처를 시연하면서 숫자 키(0~6)로 실시간 라벨링
python3 training/record_data.py
# 세션당 5~10분, 3~5 세션 권장 (제스처별 골고루)

# (2) 학습
python3 training/train.py --epochs 60
# -> config/gesture_confirm.pt

# (3) intent_node 재시작 -> 자동으로 모델 모드 전환
```

## 안전 사항

- **Thumb_Down(즉시 정지)은 모델을 거치지 않고 항상 규칙으로 처리**됩니다
- 작업 공간 한계(WS_MIN/WS_MAX) 밖의 목표는 자동 거부
- 파지 중 ABORT 시 그리퍼는 닫힌 상태 유지 (물체 낙하 방지)
- 첫 가동 시 로봇 주변에 사람이 없는 상태에서 MOVE_SPEED(기본 30%)로 테스트

## 알려진 한계 (연구용 단순화)

- 모션 완료를 시간 대기(SETTLE_TIME)로 처리 → 정밀 제어가 필요하면
  `GetArmEndPoseMsgs()` 폴링으로 위치 도달 판정으로 교체
- 뎁스는 SGBM 기반이라 무늬 없는 표면에서 구멍 발생 가능
  → 작업 물체 아래에 텍스처 있는 매트를 깔면 개선
- 그리퍼 파지력은 고정값(GRIPPER_EFFORT) → 물체별 조정 필요

## 기여하기

작업 전 [CONTRIBUTING.md](CONTRIBUTING.md)에서 브랜치 전략과 담당 영역을 확인하세요.
버그·할 일은 [Issues](../../issues)에 등록합니다.

## 관련 문서

- [CONTRIBUTING.md](CONTRIBUTING.md) — 브랜치 전략, 커밋 규칙, 원격 협업 흐름
- `config/.gitkeep` — 캘리브레이션·모델 파일이 저장되는 위치 안내
