# 협업 가이드

4인 팀(이헌재, 조우택, 주현태, 황태훈) + 미국-한국 원격 협업을 위한 규칙입니다.

## 브랜치 전략

복잡한 전략 대신 **패키지 단위로 브랜치를 나누는 단순한 방식**을 씁니다.

```
main                        항상 실행 가능한 상태 유지
├── feature/perception       hri_perception (의도 인식, gaze 변환)
├── feature/control           hri_control (Piper 제어)
├── feature/quest              hri_quest, unity/
└── feature/camera              hri_camera, calibration/
```

작업 시작 전:
```bash
git checkout main
git pull
git checkout -b feature/perception   # 본인 담당 브랜치
```

작업 끝나면 main으로 병합:
```bash
git add .
git commit -m "설명"
git push -u origin feature/perception

# GitHub 웹사이트에서 Pull Request 생성 → 리뷰 후 main에 merge
```

## 담당 영역 (겹치는 파일 최소화)

| 담당자 | 폴더 |
|--------|------|
| 이헌재 | `src/hri_perception/`, `training/` |
| 조우택 | `training/`, `calibration/` |
| 주현태 | `src/hri_control/`, `src/hri_bringup/` |
| 황태훈 | `unity/`, `src/hri_quest/`, `src/hri_camera/` |

같은 파일을 동시에 수정하지 않는 게 충돌을 막는 가장 확실한 방법입니다.
다른 사람 영역을 고쳐야 하면 먼저 팀 채널에 공유하세요.

## 커밋 메시지 규칙

```
[패키지명] 무엇을 왜 바꿨는지 한 줄로

예:
[hri_perception] fixation 판정 임계값 3cm→2cm로 조정 (오검출 감소)
[hri_control] PLACE 시퀀스에 접근 높이 파라미터 추가
[unity] GestureClassifier Pinch 임계값 0.85→0.8 완화
```

## Pull Request 체크리스트

병합 전에 아래를 확인하세요.

- [ ] `python3 -m py_compile <수정한 파일>` 문법 검사 통과
- [ ] 다른 사람 담당 폴더를 건드리지 않았는지 확인
- [ ] `config/*.pt`, `*.npz`, `*.npy` 같은 개인 캘리브레이션·모델 파일을 실수로 커밋하지 않았는지 확인
- [ ] 커밋 메시지가 무엇을 바꿨는지 설명하는지

## 원격(미국)-현장(한국) 협업 흐름

하드웨어가 필요 없는 작업(모델 구조, 로직 수정, 문서화)은 원격에서,
하드웨어 검증(실제 로봇 동작, 캘리브레이션, Quest 페어링)은 현장에서 진행합니다.

```
[미국] 코드 수정 → push → PR 생성
                              ↓
[한국] pull → 하드웨어에서 실행 → 결과 로그 공유
                              ↓
[미국] 로그 보고 다음 수정 방향 결정
```

실행 결과는 `ros2 topic echo` 출력을 캡처해서 PR 코멘트나 팀 채널에 공유해주세요.
아래 항목을 캡처하면 원격에서도 문제를 진단할 수 있습니다.

```bash
ros2 topic echo /quest/gesture --once
ros2 topic echo /gaze/target_3d --once
ros2 topic echo /intent/command --once
ros2 topic hz /camera/left/image_raw
```

## 이슈(Issue) 활용

버그나 할 일은 GitHub Issues에 등록합니다.

- 제목에 패키지명 표시: `[hri_control] ABORT 후 그리퍼 상태 복구 안 됨`
- 라벨 활용: `bug`, `hardware-needed`(하드웨어 필요), `remote-ok`(원격 가능)
- `hardware-needed` 라벨이 붙은 이슈는 한국 팀이, 나머지는 누구나 가능
