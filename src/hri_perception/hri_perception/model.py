#!/usr/bin/env python3
"""
model.py
제스처 확정 모델: GRU 인코더 x2 + Cross-Attention 융합

역할: 30프레임 시퀀스를 보고 "지금 확정해도 되는 제스처"를 출력
  - 전환 중이거나 노이즈인 프레임은 NONE으로 분류
  - gaze 움직임 패턴을 참조해서 의도가 완성됐는지 판단
    (예: 주먹을 쥐었어도 시선이 아직 흔들리면 확정 보류)

입력:
  gesture_seq (B, 30, 7) : 제스처 원핫(6) + 신뢰도(1)
  gaze_seq    (B, 30, 4) : 정규화 x,y,z + fixation(1)
출력:
  logits (B, 7) : NONE + 6개 제스처 분류
"""
import torch
import torch.nn as nn

# 출력 클래스: 0=NONE(확정 보류), 1~6=확정 제스처
CLASSES = ['NONE', 'Open_Palm', 'Pointing_Up', 'Closed_Fist',
           'Victory', 'Pinch', 'Thumb_Down']

# 입력 원핫 인코딩 순서 (Unity가 보내는 레이블)
GESTURE_IDX = {
    'Open_Palm':   0,
    'Pointing_Up': 1,
    'Closed_Fist': 2,
    'Victory':     3,
    'Pinch':       4,
    'Thumb_Down':  5,
}

SEQ_LEN     = 30
GESTURE_DIM = 7   # onehot 6 + confidence 1
GAZE_DIM    = 4   # x, y, z, fixation

# 작업 공간 정규화 범위 (로봇 base 기준, 미터) - 환경에 맞게 수정
WS_MIN = [-0.1, -0.5, -0.1]
WS_MAX = [ 0.7,  0.5,  0.6]


def encode_gesture_frame(label: str, conf: float):
    """제스처 레이블 + 신뢰도 -> (7,) 벡터"""
    v = [0.0] * GESTURE_DIM
    idx = GESTURE_IDX.get(label, 0)
    v[idx] = 1.0
    v[6] = float(conf)
    return v


def encode_gaze_frame(x: float, y: float, z: float, fixation: bool):
    """로봇 좌표 + fixation -> 정규화 (4,) 벡터"""
    out = []
    for val, lo, hi in zip((x, y, z), WS_MIN, WS_MAX):
        out.append((val - lo) / (hi - lo))
    out.append(1.0 if fixation else 0.0)
    return out


class GestureConfirmModel(nn.Module):
    def __init__(self, hidden=96, n_classes=len(CLASSES)):
        super().__init__()
        self.g_enc = nn.GRU(GESTURE_DIM, hidden, num_layers=2,
                            batch_first=True, dropout=0.2)
        self.z_enc = nn.GRU(GAZE_DIM, hidden, num_layers=2,
                            batch_first=True, dropout=0.2)

        # 제스처(Q)가 gaze(K,V)를 참조:
        # "이 동작 의도가 형성되는 동안 시선이 안착했는가"
        self.attn = nn.MultiheadAttention(hidden, num_heads=4,
                                          batch_first=True)
        self.norm = nn.LayerNorm(hidden)

        self.head = nn.Sequential(
            nn.Linear(hidden, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, n_classes),
        )

    def forward(self, gesture_seq, gaze_seq):
        g, _ = self.g_enc(gesture_seq)            # (B, T, H)
        z, _ = self.z_enc(gaze_seq)               # (B, T, H)
        fused, _ = self.attn(query=g, key=z, value=z)
        fused = self.norm(fused + g)              # residual
        feat = fused[:, -1, :]                    # 마지막 타임스텝
        return self.head(feat)                    # (B, n_classes)
