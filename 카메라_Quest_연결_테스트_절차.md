# 카메라 · Quest Pro 연결 테스트 절차

> 로봇팔 없이 스테레오 카메라와 MetaQuest Pro가 정상적으로 연결·통신하는지
> 확인하는 절차입니다. 순서대로 진행하세요.
>
> **진행 순서 안내**: 캘리브레이션은 뎁스·시선 3D 좌표의 "정확도"에만
> 영향을 줍니다. 영상 스트리밍, 제스처 인식, 화면상 시선 좌표는 캘리브레이션
> 없이도 확인 가능하므로, 이 문서는 **먼저 캘리브레이션 없이 연결 자체를
> 빠르게 확인**하고, **그다음 캘리브레이션으로 정확도를 검증**하는 순서로
> 구성했습니다.

---

## 0. 실행 환경 선택 (중요 — 먼저 확인)

이 프로젝트는 **Ubuntu 22.04 + ROS2 Humble** 기준으로 만들어졌습니다.

| PC 상황 | 방법 |
|---------|------|
| Ubuntu 22.04가 이미 설치됨 | 아래 "A. 네이티브 환경"으로 진행 |
| Ubuntu 26.04 등 다른 버전이 이미 설치됨 (재설치 원치 않음) | 아래 "B. Docker 환경"으로 진행 |

두 방법 모두 **1단계 이후 절차는 완전히 동일**합니다. 차이는 ROS2가
어디서 실행되느냐(호스트 OS 위 vs 컨테이너 안)뿐입니다.

### A. 네이티브 환경 (Ubuntu 22.04)

별도 설정 없이 1단계로 바로 이동하세요.

### B. Docker 환경 (Ubuntu 26.04 등 다른 버전)

호스트 OS는 그대로 두고, Docker 컨테이너 안에 Ubuntu 22.04 + ROS2 Humble을
띄워서 그 안에서 작업합니다. 카메라(USB)와 네트워크(Quest 통신)를 컨테이너에
그대로 연결하므로 기능상 차이는 없습니다.

**B-1. Docker 설치**

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker   # 적용 안 되면 로그아웃 후 재로그인
```

**B-2. 카메라 장치 이름 확인** (컨테이너 실행 전 호스트에서)

```bash
ls /dev/video*
# 예: /dev/video0  /dev/video1
```

**B-3. GitHub 저장소를 호스트에 먼저 clone**

```bash
git clone https://github.com/Heonjaelee/hri-pick-and-place.git ~/hri-pick-and-place
```

**B-4. ROS2 Humble 컨테이너 실행**

```bash
docker run -it \
  --name hri-dev \
  --network host \
  --device=/dev/video0 \
  --device=/dev/video1 \
  -v ~/hri-pick-and-place:/root/hri_robot_ws \
  osrf/ros:humble-desktop \
  bash
```

- `--network host` : Quest Pro가 WebSocket으로 접속할 수 있도록 컨테이너가
  호스트와 같은 네트워크를 사용
- `--device=/dev/videoN` : B-2에서 확인한 실제 장치 번호로 맞추기
- `-v ~/hri-pick-and-place:/root/hri_robot_ws` : 코드 폴더를 컨테이너와 공유
  (호스트에서 `git pull` 하면 컨테이너 안에도 바로 반영됨)

컨테이너 안 프롬프트가 `root@...:/#` 형태로 바뀌면 진입 성공입니다.
이제 아래 1단계부터는 **이 컨테이너 안에서** 그대로 진행하세요.

```bash
cd /root/hri_robot_ws
```

**B-5. 다음에 다시 쓸 때 (컨테이너 재사용)**

한 번 만든 컨테이너는 삭제하지 않는 한 재시작만 하면 됩니다.

```bash
docker start -ai hri-dev
```

새 터미널을 하나 더 열어서 같은 컨테이너에 동시 접속하려면:

```bash
docker exec -it hri-dev bash
```

(카메라 노드, Quest 브릿지 노드 등을 여러 터미널에서 동시에 띄워야 하므로
아래 단계에서 이 명령을 반복해서 사용합니다.)

---

## 0-1. 카메라 · Quest Pro 물리적 연결 방식

본격적인 절차 전에, 두 장치가 PC와 어떻게 연결되는지 먼저 이해하고 시작하세요.
연결 방식이 서로 완전히 다릅니다.

### 카메라 — 유선 (USB)

oCamS-1CGN-U는 **USB 3.0 케이블로 PC에 직접 연결**합니다. 어댑터나 별도
설정 없이 USB 포트에 꽂으면 리눅스가 `/dev/video0`, `/dev/video1` 형태로
자동 인식합니다. PC가 카메라 영상을 받아서 처리하는 쪽입니다.

### Quest Pro — 무선 (같은 Wi-Fi)

Quest Pro는 케이블 연결이 아니라 **Wi-Fi 네트워크로 PC와 통신**합니다.
케이블은 오직 **앱을 빌드해서 기기에 설치할 때**(Unity에서 Build And Run
할 때)만 USB로 잠깐 연결하고, 실제 동작 중에는 무선입니다.

핵심 조건: **Quest Pro와 PC가 반드시 같은 Wi-Fi에 연결되어 있어야 합니다.**
서로 다른 네트워크에 있으면 연결 자체가 되지 않습니다.

### 통신이 이루어지는 실제 경로

PC에서 ROS2 노드들이 두 개의 포트를 열어두고, Quest 앱이 그 포트로
접속하는 구조입니다.

- **8765번 포트**: PC → Quest, 카메라 영상 전송 (`stream_node`)
- **8766번 포트**: Quest → PC, 시선·제스처 데이터 전송 (`quest_bridge_node`)

Unity 스크립트(`QuestSender.cs`, `VideoReceiver.cs`)에 PC의 IP 주소
(`hostname -I`로 확인, 3-3절 참고)를 미리 입력해둬야 Quest가 어디로
접속할지 알 수 있습니다.

### 요약

| | 연결 방식 | 케이블 필요 시점 |
|---|---|---|
| 카메라 | USB 3.0 유선, PC에 직결 | 항상 (상시 연결) |
| Quest Pro | Wi-Fi 무선 | 앱 빌드할 때만 (일시적) |

방화벽이 8765, 8766 포트를 막고 있으면 연결이 안 되므로, 4단계에서
안내하는 `sudo ufw allow 8765`, `sudo ufw allow 8766`을 미리 기억해두세요.

---

## 1. 저장소 다운로드 및 빌드

> Docker 환경(B)이라면 이미 B-3에서 clone했고 컨테이너 안에서
> `/root/hri_robot_ws`로 이동한 상태이므로 clone은 생략하고 의존성 설치부터
> 진행하세요.

```bash
# 네이티브 환경(A)이라면 여기서 clone
git clone https://github.com/Heonjaelee/hri-pick-and-place.git
cd hri-pick-and-place

# ROS2 의존성 설치
sudo apt update
sudo apt install ros-humble-cv-bridge python3-colcon-common-extensions -y

# Python 의존성 설치
pip install -r requirements.txt --break-system-packages

# 빌드
colcon build --symlink-install
source install/setup.bash
```

**확인**: 에러 없이 `colcon build`가 끝나고 `Summary: 6 packages finished` 같은
메시지가 나오면 성공입니다.

---

## 2. 카메라 단독 테스트

Quest를 붙이기 전에 카메라 자체가 인식되는지 먼저 확인합니다.
**이 단계는 캘리브레이션이 필요 없습니다.**

```bash
# 카메라가 인식되는지 확인
ls /dev/video*
# → /dev/video0, /dev/video1 등이 보여야 함 (oCamS는 보통 2개 장치로 잡힘)

# v4l2 정보로 실제 oCamS인지 확인
v4l2-ctl --list-devices
```

카메라가 안 잡히면:
```bash
lsusb | grep -i "with"     # WithRobot 문자열이 보이면 인식된 것
```

> Docker 환경인데 카메라가 안 보이면, 컨테이너를 B-4의 `--device` 옵션이
> 정확한 장치 번호로 다시 실행됐는지 확인하세요. (`docker rm hri-dev` 후 재실행)

카메라 노드만 단독 실행:
```bash
ros2 run hri_camera camera_node
```

터미널에 `캘리브레이션 파일 없음 - 기본 파라미터 사용`이라는 경고가 뜰 수
있는데, **이 단계에서는 정상**입니다. 영상 자체는 문제없이 나옵니다.

다른 터미널에서 영상 확인:
```bash
# 네이티브 환경(A)
sudo apt install ros-humble-rqt-image-view
ros2 run rqt_image_view rqt_image_view

# Docker 환경(B) — 새 터미널에서 컨테이너에 재접속 후 실행
docker exec -it hri-dev bash
source /opt/ros/humble/setup.bash
ros2 run rqt_image_view rqt_image_view
```

**확인**: rqt_image_view 창에서 `/camera/left/image_raw` 토픽을 선택했을 때
실제 영상이 보이면 성공.

```bash
ros2 topic hz /camera/left/image_raw
# → 25~30Hz 근처면 정상
```

카메라 노드는 계속 켜둔 채로 다음 단계로 넘어갑니다.

---

## 3. Unity 앱 빌드 (Quest Pro용)

이 단계는 Unity가 설치된 PC(카메라 연결 PC와 달라도 무방)에서 진행합니다.
Docker와 무관하게 항상 **호스트 OS(또는 별도 PC)** 에서 직접 진행합니다.
**이 단계도 캘리브레이션과 무관합니다.**

### 3-1. 프로젝트 준비

1. Unity 2022 LTS로 새 프로젝트 생성 (3D 템플릿)
2. Package Manager에서 **Meta XR All-in-One SDK** 설치
3. GitHub에서 받은 아래 3개 스크립트를 `Assets/Scripts/`에 복사
   - `unity/GestureClassifier.cs`
   - `unity/QuestSender.cs`
   - `unity/VideoReceiver.cs`
4. [NativeWebSocket](https://github.com/endel/NativeWebSocket) 패키지 설치
   (Package Manager → Add package from git URL →
   `https://github.com/endel/NativeWebSocket.git#upm`)

### 3-2. 씬 구성

1. `OVRCameraRig` 프리팹을 씬에 배치
2. `OVRCameraRig` 하위에 `OVREyeGaze` 컴포넌트 추가
3. 오른손 트래킹 오브젝트에 `OVRHand` + `OVRSkeleton` 컴포넌트 확인 후
   **GestureClassifier.cs** 붙이기
4. Canvas(World Space) 생성 → 그 안에 RawImage 배치 (이름: `VideoScreen`)
   → **VideoReceiver.cs** 붙이고 `videoScreen` 필드에 RawImage 연결
5. 빈 GameObject 생성(`QuestSenderObject`) → **QuestSender.cs** 붙이고
   Inspector에서 다음 연결:
   - `eyeGaze` → OVREyeGaze 컴포넌트
   - `videoScreen` → 위에서 만든 RawImage의 RectTransform
   - `gesture` → GestureClassifier가 붙은 오브젝트
   - (선택) `gazeCursor` → 시선 피드백용 UI 이미지

### 3-3. IP 주소 설정

카메라 연결된 PC(네이티브든 Docker 호스트든 동일)의 IP를 확인합니다.

```bash
hostname -I
# 예: 192.168.0.15
```

> Docker 환경이라도 `--network host`로 실행했다면 컨테이너가 호스트와
> IP를 공유하므로, 위에서 확인한 호스트 IP를 그대로 쓰면 됩니다.

Unity에서:
- `QuestSender.cs`의 `pcAddress` → `ws://192.168.0.15:8766`
- `VideoReceiver.cs`의 `pcAddress` → `ws://192.168.0.15:8765`

(IP는 실제 확인한 값으로 교체)

> **팀 공유 팁**: 이 IP는 빌드 시점에 고정되므로, 완성된 APK 파일을
> GitHub에 그대로 올려서 공유하는 방식은 추천하지 않습니다. 대신 Unity
> **프로젝트 자체**(Assets, ProjectSettings 등)를 저장소에 커밋해두면,
> 팀원 각자가 자기 PC의 IP로 직접 빌드할 수 있습니다. 빌드된 APK를 굳이
> 공유해야 한다면 저장소 커밋 대신 GitHub **Releases** 기능을 사용하세요.

### 3-4. 빌드 및 설치

1. File → Build Settings → Platform을 **Android**로 전환 (Switch Platform)
2. Player Settings → XR Plug-in Management에서 **Oculus** 체크
3. Quest Pro를 USB로 PC에 연결, 기기에서 "USB 디버깅 허용" 팝업 승인
4. Build And Run 클릭

**확인**: Quest Pro 기기에 앱이 설치되고 자동 실행됩니다. 최초 실행 시
Eye Tracking, Hand Tracking 권한 팝업이 뜨면 **모두 허용**하세요.

---

## 4. 1차 연결 확인 (캘리브레이션 없이)

카메라 노드는 2단계에서 계속 켜둔 상태여야 합니다. 아래 노드들을 추가로 실행합니다.

Docker 환경이면 터미널마다 아래로 컨테이너에 접속한 뒤 진행하세요.
```bash
docker exec -it hri-dev bash
cd /root/hri_robot_ws && source install/setup.bash
```

```bash
# 터미널 2
ros2 run hri_quest stream_node

# 터미널 3
ros2 run hri_quest quest_bridge_node
```

방화벽이 막고 있다면 포트를 열어줍니다. (Docker 환경이면 호스트 OS에서 실행)
```bash
sudo ufw allow 8765
sudo ufw allow 8766
```

이제 **Quest Pro에서 빌드한 앱을 실행**합니다.

### 확인해야 할 것 (Quest Pro 화면)

- [ ] Quest 화면에 **카메라 영상이 실시간으로 보임** (약간의 지연은 정상)
- [ ] 화면 위에 **시선 커서**가 표시되고, 눈을 움직이면 커서도 따라 움직임
- [ ] 손을 펴고 접어보며 제스처에 반응이 있는지

### 확인해야 할 것 (터미널) — 여기까지는 캘리브레이션 불필요

```bash
# Quest에서 제스처 데이터가 오는지
ros2 topic echo /quest/gesture
# → 손을 쥐었다 폈다 하면 "Open_Palm", "Closed_Fist" 등으로 값이 바뀌어야 함

ros2 topic echo /quest/gesture_confidence

# 시선 정규화 좌표 확인 (화면 픽셀 좌표, 캘리브레이션 무관)
ros2 topic echo /quest/gaze
# → 화면을 좌우로 보면 x값이, 위아래로 보면 y값이 0~1 사이에서 바뀌어야 함
```

```bash
ros2 topic hz /camera/left/image_raw    # ~30Hz
ros2 topic hz /quest/gaze               # ~30Hz
```

**여기까지 전부 정상이면 "연결" 자체는 확인 완료입니다.**
이제 뎁스·3D 좌표의 "정확도"를 위해 캘리브레이션을 진행합니다.

---

## 5. 스테레오 캘리브레이션 (필수, 최초 1회)

체커보드를 준비하고 진행합니다. 4단계에서 켜둔 `stream_node`,
`quest_bridge_node`는 그대로 둬도 되지만, `camera_node`는 잠시
끄고(`Ctrl+C`) 진행하세요 (같은 카메라 장치를 중복 사용할 수 없음).

```bash
python3 calibration/calibrate_stereo.py --device 0 --square 0.025
```

- 화면에 좌/우 영상이 나란히 뜹니다
- 체커보드를 화면 안에서 **다양한 각도·거리·위치**로 비추며 스페이스바로 캡처
- 최소 10장, 권장 20장 이상
- 캡처 후 `c` 키를 누르면 계산 시작 → `config/stereo_params.npz` 저장됨

**확인**: 터미널에 `RMS 오차: 0.X px` 값이 출력됩니다. 1.0 이하면 양호,
2.0 이상이면 다시 촬영을 권장합니다.

```bash
ls -la config/stereo_params.npz   # 파일 생성 확인
```

> Docker 환경이라면 화면(GUI)이 컨테이너 밖으로 표시되지 않을 수 있습니다.
> 안 뜨면 아래를 컨테이너 실행 전 호스트에서 한 번 실행한 뒤 B-4의
> `docker run` 명령에 `-e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix`
> 옵션을 추가해서 다시 실행하세요.
> ```bash
> xhost +local:docker
> ```

캘리브레이션이 끝나면 `camera_node`를 다시 실행합니다.

```bash
ros2 run hri_camera camera_node
```

이번엔 경고 없이 `캘리브레이션 적용: f=... B=...` 로그가 뜨면 성공입니다.

---

## 6. 2차 연결 확인 (캘리브레이션 반영 후 정확도 검증)

나머지 인식 노드를 마저 실행합니다.

```bash
ros2 run hri_perception gaze_to_3d_node
```

```bash
# 시선이 3D 좌표로 잘 변환되는지 (뎁스가 있는 물체를 응시해야 값이 나옴)
ros2 topic echo /gaze/target_3d

# fixation(시선 고정) 판정 확인
ros2 topic echo /gaze/fixation
# → 한 곳을 계속 보면 true, 시선을 움직이면 false
```

**확인 포인트**:
- 물체가 있는 곳을 응시했을 때만 `/gaze/target_3d`에 값이 나와야 함 (무늬 없는 빈 벽은 값이 안 나올 수 있음 — 정상)
- 한 지점을 2~3초 계속 보면 `/gaze/fixation`이 `true`로 바뀌어야 함
- 캘리브레이션 전에는 좌표가 들쭉날쭉했다면, 캘리브레이션 후에는 값이 안정적으로 나오는지 비교

---

## 7. 최종 체크리스트

| 항목 | 확인 방법 | 정상 기준 | 캘리브레이션 필요 |
|------|-----------|-----------|:---:|
| 실행 환경 결정 | 네이티브 22.04 또는 Docker 컨테이너 | 0단계에서 선택 완료 | - |
| 카메라 인식 | `ls /dev/video*` | 장치 2개 표시 | ✗ |
| 카메라 영상 발행 | `ros2 topic hz /camera/left/image_raw` | ~30Hz | ✗ |
| Unity 앱 빌드·설치 | Quest 기기에서 실행 확인 | 앱 실행됨 | ✗ |
| Quest→PC 연결 | 터미널에 "Quest Pro 연결됨" 로그 | 로그 출력됨 | ✗ |
| Quest 화면 영상 | Quest 헤드셋 착용 후 육안 확인 | 카메라 영상 실시간 표시 | ✗ |
| 제스처 인식 | `ros2 topic echo /quest/gesture` | 손 모양 따라 값 변경 | ✗ |
| 시선 화면 좌표 | `ros2 topic echo /quest/gaze` | 시선 따라 x,y 변경 | ✗ |
| 스테레오 캘리브레이션 | `config/stereo_params.npz` 존재 | 파일 있음, RMS < 1.0 | - |
| gaze 3D 변환 | `ros2 topic echo /gaze/target_3d` | 뎁스 있는 곳 응시 시 좌표 출력 | ✓ |
| fixation 판정 | `ros2 topic echo /gaze/fixation` | 응시 유지 시 true | ✓ |

전부 체크되면 카메라·Quest 연결 테스트는 성공입니다.
다음 단계는 로봇팔 납품 후 `calibrate_cam_to_robot.py`와
`hri_control` 패키지 연동입니다.

---

## 자주 발생하는 문제

**Quest 앱이 켜졌는데 화면이 검은색**
→ `stream_node`가 실행 중인지, PC IP가 정확한지 확인. 방화벽도 재점검.

**"Quest Pro 연결됨" 로그가 안 뜸**
→ Quest와 PC가 같은 Wi-Fi인지 확인 (특히 회사/학교 Wi-Fi는 기기 간 통신을
막는 경우가 많음 — 개인 핫스팟이나 공유기로 테스트 권장)

**제스처가 항상 Open_Palm으로만 나옴**
→ Quest 설정에서 Hand Tracking이 활성화됐는지 확인. 손이 카메라 시야
밖에 있어도 이런 증상이 나타남.

**캘리브레이션 전인데 뎁스·3D 좌표가 이상함**
→ 4단계까지는 정상입니다. 캘리브레이션 전에는 뎁스 정확도가 낮은 게
기본 동작이며, 5단계 캘리브레이션 이후 6단계에서 정확도를 확인합니다.

**캘리브레이션 후에도 뎁스가 전부 0으로 나옴**
→ `config/stereo_params.npz`가 실제로 생성됐는지, `camera_node`를
캘리브레이션 이후 재시작했는지 확인. 무늬 없는 평평한 벽을 보면 뎁스가
안 잡히므로 물체가 있는 곳을 응시하며 테스트.

**시선 커서가 화면과 다르게 움직임**
→ `QuestSender.cs`의 `videoScreen` 참조가 실제 카메라 영상이 표시되는
RawImage와 정확히 연결됐는지 확인.

**(Docker) 컨테이너 안에서 카메라 장치를 못 찾음**
→ `docker run` 실행 시 `--device` 옵션의 번호가 실제 `/dev/video*`와
다를 수 있음. `docker rm hri-dev`로 컨테이너 삭제 후 올바른 번호로 재실행.

**(Docker) 캘리브레이션 창(GUI)이 안 뜸**
→ 5단계 안내대로 호스트에서 `xhost +local:docker` 실행 후, 컨테이너를
`-e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix` 옵션 추가해서
재실행.

**(Docker) `ros2 topic echo`가 다른 터미널의 노드를 못 봄**
→ 같은 컨테이너(`docker exec -it hri-dev bash`)로 접속했는지 확인.
서로 다른 `docker run`으로 컨테이너를 여러 개 만들면 네트워크가 분리되어
토픽이 안 보일 수 있음. 항상 `docker exec`로 기존 컨테이너에 접속할 것.
