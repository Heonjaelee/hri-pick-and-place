# Contributing Guide

**English** | [한국어](CONTRIBUTING.md)

Rules for the 4-person team (Heonjae Lee, Wootaek Cho, Hyuntae Ju, Taehun Hwang)
collaborating remotely between the US and Korea.

## Branching Strategy

Instead of a complex strategy, we use a simple **one branch per package** approach.

```
main                        always kept in a runnable state
├── feature/perception       hri_perception (intent recognition, gaze transform)
├── feature/control           hri_control (Piper control)
├── feature/quest              hri_quest, unity/
└── feature/camera              hri_camera, calibration/
```

Before starting work:
```bash
git checkout main
git pull
git checkout -b feature/perception   # your assigned branch
```

When work is done, merge into main:
```bash
git add .
git commit -m "description"
git push -u origin feature/perception

# Open a Pull Request on the GitHub website → review → merge into main
```

## Area Ownership (minimizing overlapping files)

| Owner | Folders |
|-------|---------|
| Heonjae Lee | `src/hri_perception/`, `training/` |
| Wootaek Cho | `training/`, `calibration/` |
| Hyuntae Ju | `src/hri_control/`, `src/hri_bringup/` |
| Taehun Hwang | `unity/`, `src/hri_quest/`, `src/hri_camera/` |

Not editing the same file at the same time is the most reliable way to
avoid merge conflicts. If you need to modify another member's area, share
it in the team channel first.

## Commit Message Convention

```
[package name] one-line description of what changed and why

Examples:
[hri_perception] adjusted fixation threshold from 3cm to 2cm (reduces false positives)
[hri_control] added approach-height parameter to the PLACE sequence
[unity] relaxed GestureClassifier Pinch threshold from 0.85 to 0.8
```

## Pull Request Checklist

Confirm the following before merging:

- [ ] `python3 -m py_compile <changed file>` passes syntax check
- [ ] You haven't touched another member's owned folders
- [ ] You haven't accidentally committed personal calibration/model files
      such as `config/*.pt`, `*.npz`, `*.npy`
- [ ] The commit message explains what was changed

## Remote (US) - On-site (Korea) Collaboration Flow

Work that doesn't require hardware (model architecture, logic changes,
documentation) is done remotely; hardware verification (actual robot
motion, calibration, Quest pairing) is done on-site.

```
[US] Modify code → push → open PR
                              ↓
[Korea] pull → run on hardware → share result logs
                              ↓
[US] Review logs → decide next steps
```

Please capture `ros2 topic echo` output and share it in the PR comments or
team channel. Capturing the following lets problems be diagnosed remotely:

```bash
ros2 topic echo /quest/gesture --once
ros2 topic echo /gaze/target_3d --once
ros2 topic echo /intent/command --once
ros2 topic hz /camera/left/image_raw
```

## Using Issues

File bugs and tasks in GitHub Issues.

- Prefix the title with the package name: `[hri_control] Gripper state not restored after ABORT`
- Use labels: `bug`, `hardware-needed`, `remote-ok`
- Issues labeled `hardware-needed` should be picked up by the Korea team;
  everything else is open to anyone
