# HRI Pick & Place System

**English** | [한국어](README.md)

> 2026 UGRP Undergraduate Research Project · User-Interactive Multimodal Robotic Display Control System

A research project that controls a Piper robot arm (with gripper) to perform
pick and place tasks, driven by gaze tracking and hand gestures from a
MetaQuest Pro headset.

- **Gaze = WHERE**: The Quest Pro displays footage from a stereo camera
  (oCamS-1CGN-U) capturing the workspace. Wherever the operator looks on
  that screen is converted into a 3D target position in the robot's
  coordinate frame.
- **Gesture = WHAT**: Six hand gestures, classified from Quest Pro hand
  tracking, determine which robot action to perform.

## Team & Current Status

| Role | Member | Area |
|------|--------|------|
| Lead · Intent recognition model | Heonjae Lee | `hri_perception`, deep learning model |
| Data · Evaluation | Wootaek Cho | `training`, performance evaluation |
| Robot control | Hyuntae Ju | `hri_control`, `hri_bringup` |
| Quest · Camera | Taehun Hwang | `unity`, `hri_quest`, `hri_camera` |

**Hardware status**: Procurement paperwork for the AgileX PiPer with Gripper
is complete; delivery is pending (awaiting a comparative quote from the
supplier). The stereo camera and Quest Pro have already been purchased.

The software is designed so the full pipeline can be verified in
**simulation mode** even without the robot arm — `piper_controller_node`
automatically falls back to a log-only mode when `piper_sdk` is not
installed. See [CONTRIBUTING.md](CONTRIBUTING.md) for how the team divides
and coordinates work (guide currently in Korean).

## Gesture Mapping (finalized)

| Gesture | Robot action | Gaze usage |
|---|---|---|
| Open_Palm | Idle | Ignored |
| Pointing_Up (index finger) | Move | Target position |
| Closed_Fist | Grasp / carry while moving | Grasp·move position |
| Victory | Place | Placement position |
| Pinch (thumb + index) | Return home | Ignored |
| Thumb_Down | Immediate stop | Ignored |

## Directory Structure

```
hri_robot_ws/
├── unity/            # Quest Pro Unity scripts (3)
├── calibration/      # Calibration scripts (2)
├── training/         # Data collection + model training
├── config/           # Calibration results + trained model (generated)
└── src/              # 6 ROS2 packages
    ├── hri_msgs        Custom message (RobotIntent)
    ├── hri_camera      camera_node: publishes RGB + depth
    ├── hri_quest       quest_bridge_node, stream_node
    ├── hri_perception  gaze_to_3d_node, intent_node (+ model)
    ├── hri_control     piper_controller_node (incl. gripper)
    └── hri_bringup     full-system launch
```

## 1. PC Environment Setup (Ubuntu 22.04 + ROS2 Humble)

```bash
# ROS2 dependencies
sudo apt install ros-humble-cv-bridge python3-colcon-common-extensions

# Python dependencies
pip install -r requirements.txt

# Piper CAN connection (USB-CAN adapter)
sudo ip link set can0 up type can bitrate 1000000

# Build
cd ~/hri_robot_ws
colcon build --symlink-install
source install/setup.bash
```

## 2. Unity (Quest Pro) Setup

1. Install Unity 2022 LTS + Meta XR All-in-One SDK
2. Enable Eye Tracking and Hand Tracking permissions in project settings
   (tracking must also be allowed on the Quest Pro device itself)
3. Add the [NativeWebSocket](https://github.com/endel/NativeWebSocket) package
4. Scene setup:
   - `OVRCameraRig` + `OVREyeGaze` component
   - On the right hand: `OVRHand` + `OVRSkeleton` + **GestureClassifier.cs**
   - In front of the operator: a World Space Canvas + RawImage (videoScreen)
     + **VideoReceiver.cs**
   - On an empty object: **QuestSender.cs** (wire up eyeGaze, videoScreen, gesture)
5. Set `pcAddress` in both scripts to the PC's IP address, then build to Quest Pro

## 3. Calibration (one-time)

```bash
# (1) Stereo calibration — requires a 9x6 checkerboard
python3 calibration/calibrate_stereo.py --device 0 --square 0.025
# -> config/stereo_params.npz

# (2) Camera-to-robot coordinate calibration
#     click a marker -> touch the robot end-effector to the marker -> Enter, 4-6 points
python3 calibration/calibrate_cam_to_robot.py --device 0
# -> config/cam_to_robot.npy
```

Adjust `WS_MIN`/`WS_MAX` (workspace bounds) in
`src/hri_perception/hri_perception/model.py` and `intent_node.py` to match
your actual environment.

## 4. Running the System

```bash
source install/setup.bash
ros2 launch hri_bringup hri_system.launch.py
```

Then launch the Quest Pro app — once the camera feed appears on screen,
the connection is working.

**The system runs immediately in rule-based mode** (a gesture is confirmed
after being held for 0.5s with gaze fixation). The full pipeline can be
verified even before the model is trained.

### Commands for checking the system is working

```bash
ros2 topic hz /camera/left/image_raw     # should be near 30Hz
ros2 topic echo /quest/gesture            # confirm gesture data is arriving from Quest
ros2 topic echo /gaze/target_3d           # confirm gaze 3D coordinates
ros2 topic echo /intent/command           # confirm final robot commands
ros2 topic echo /robot/state              # robot sequence state
```

## 5. Training the Deep Learning Model (optional — improves responsiveness)

Rule-based mode has a fixed delay (0.5s), whereas the GRU + Cross-Attention
model looks at both the gesture-formation pattern and gaze settling
together, allowing faster and smoother confirmation.

```bash
# (1) Collect data while the system is running
#     Perform gestures while labeling in real time with number keys (0-6)
python3 training/record_data.py
# 5-10 minutes per session, 3-5 sessions recommended (spread across gestures)

# (2) Train
python3 training/train.py --epochs 60
# -> config/gesture_confirm.pt

# (3) Restart intent_node -> automatically switches to model mode
```

## Safety Notes

- **Thumb_Down (immediate stop) always bypasses the model and is handled
  as a hard-coded rule**
- Targets outside the workspace bounds (WS_MIN/WS_MAX) are automatically rejected
- If ABORT occurs while grasping, the gripper stays closed (prevents dropping the object)
- For first runs, keep people clear of the robot and test at MOVE_SPEED (default 30%)

## Known Limitations (research-grade simplifications)

- Motion completion is handled via a fixed time wait (SETTLE_TIME) →
  for precise control, replace with position-reached detection via
  `GetArmEndPoseMsgs()` polling
- Depth is SGBM-based, so holes can appear on textureless surfaces →
  placing a textured mat under work objects improves this
- Gripper force is a fixed value (GRIPPER_EFFORT) → may need per-object tuning

## Contributing

Check [CONTRIBUTING.md](CONTRIBUTING.md) (Korean) for the branching
strategy and area ownership before starting work. File bugs and tasks in
[Issues](../../issues).

## Related Documents

- [CONTRIBUTING.md](CONTRIBUTING.md) — branching strategy, commit conventions,
  remote collaboration workflow (Korean)
- `config/.gitkeep` — notes on where calibration/model files are stored
