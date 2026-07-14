#!/usr/bin/env python3
"""
train.py
record_data.py 로 모은 세션 데이터로 제스처 확정 모델 학습

사용법:
  python3 train.py                    # training/data/*.npz 전부 사용
  python3 train.py --epochs 80

학습 완료 시 config/gesture_confirm.pt 저장
-> intent_node가 다음 실행부터 자동으로 모델 모드로 전환
"""
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split
import argparse, glob, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', 'src', 'hri_perception'))
from hri_perception.model import GestureConfirmModel, SEQ_LEN, CLASSES

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
OUT_PATH = os.path.expanduser('~/hri_robot_ws/config/gesture_confirm.pt')


class SeqDataset(Dataset):
    """연속 기록 -> 슬라이딩 윈도우 (T=30, stride=3)
    윈도우의 라벨 = 마지막 프레임의 라벨"""
    def __init__(self, files, stride=3):
        self.samples = []
        for f in files:
            d = np.load(f)
            g, z, y = d['gestures'], d['gazes'], d['labels']
            n = min(len(g), len(z), len(y))
            for i in range(0, n - SEQ_LEN, stride):
                self.samples.append((
                    g[i:i + SEQ_LEN],
                    z[i:i + SEQ_LEN],
                    int(y[i + SEQ_LEN - 1])))
        print(f'{len(files)}개 세션 -> {len(self.samples)}개 윈도우')

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, i):
        g, z, y = self.samples[i]
        return (torch.tensor(g, dtype=torch.float32),
                torch.tensor(z, dtype=torch.float32),
                torch.tensor(y, dtype=torch.long))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', type=int, default=60)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--batch', type=int, default=64)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(DATA_DIR, '*.npz')))
    if not files:
        print('데이터 없음 - record_data.py 먼저 실행하세요')
        return

    ds = SeqDataset(files)
    n_val = max(1, int(len(ds) * 0.15))
    tr, va = random_split(ds, [len(ds) - n_val, n_val])
    tr_loader = DataLoader(tr, batch_size=args.batch, shuffle=True)
    va_loader = DataLoader(va, batch_size=args.batch)

    # 클래스 불균형 보정 (NONE이 압도적으로 많음)
    labels = np.array([s[2] for s in ds.samples])
    counts = np.bincount(labels, minlength=len(CLASSES)).astype(np.float32)
    weights = 1.0 / np.maximum(counts, 1)
    weights = weights / weights.sum() * len(CLASSES)
    print('클래스 분포:', dict(zip(CLASSES, counts.astype(int))))

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = GestureConfirmModel().to(device)
    crit = nn.CrossEntropyLoss(
        weight=torch.tensor(weights, device=device),
        label_smoothing=0.05)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr,
                            weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs)

    best_acc = 0.0
    for ep in range(args.epochs):
        model.train()
        tl = 0.0
        for g, z, y in tr_loader:
            g, z, y = g.to(device), z.to(device), y.to(device)
            loss = crit(model(g, z), y)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            tl += loss.item()
        sched.step()

        model.eval()
        correct = total = 0
        with torch.no_grad():
            for g, z, y in va_loader:
                g, z, y = g.to(device), z.to(device), y.to(device)
                pred = model(g, z).argmax(-1)
                correct += (pred == y).sum().item()
                total += len(y)
        acc = correct / max(total, 1)
        print(f'epoch {ep+1:3d} | loss {tl/len(tr_loader):.4f} '
              f'| val acc {acc:.3f}')

        if acc > best_acc:
            best_acc = acc
            os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
            torch.save(model.state_dict(), OUT_PATH)

    print(f'\n최고 검증 정확도 {best_acc:.3f} -> {OUT_PATH} 저장')
    print('intent_node를 재시작하면 모델 모드로 동작합니다')


if __name__ == '__main__':
    main()
