#!/usr/bin/env python3
"""
calibrate_stereo.py
oCamS-1CGN-U 스테레오 캘리브레이션 (체커보드 사용)

사용법:
  1. 9x6 내부 코너 체커보드 출력 (한 칸 25mm 권장)
  2. python3 calibrate_stereo.py --device 0 --square 0.025
  3. 체커보드를 다양한 위치/각도로 비추며 스페이스바로 20장 캡처
  4. 'c' 키를 누르면 캘리브레이션 후 config/stereo_params.npz 저장
"""
import cv2
import numpy as np
import argparse
import os

CHECKER = (9, 6)   # 내부 코너 수


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', type=int, default=0)
    ap.add_argument('--square', type=float, default=0.025,
                    help='체커보드 한 칸 크기(m)')
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 2560)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    objp = np.zeros((CHECKER[0] * CHECKER[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHECKER[0], 0:CHECKER[1]].T.reshape(-1, 2)
    objp *= args.square

    obj_pts, img_l, img_r = [], [], []
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)

    print('스페이스: 캡처 / c: 캘리브레이션 / q: 종료')
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        left, right = frame[:, :1280], frame[:, 1280:]
        gl = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
        gr = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)

        fl, cl = cv2.findChessboardCorners(gl, CHECKER, None)
        fr, cr = cv2.findChessboardCorners(gr, CHECKER, None)

        disp = np.hstack([left, right]).copy()
        if fl:
            cv2.drawChessboardCorners(disp[:, :1280], CHECKER, cl, fl)
        if fr:
            cv2.drawChessboardCorners(disp[:, 1280:], CHECKER, cr, fr)
        cv2.putText(disp, f'captured: {len(obj_pts)}/20', (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow('stereo calib', cv2.resize(disp, (1280, 360)))

        k = cv2.waitKey(1) & 0xFF
        if k == ord(' ') and fl and fr:
            cl = cv2.cornerSubPix(gl, cl, (11, 11), (-1, -1), criteria)
            cr = cv2.cornerSubPix(gr, cr, (11, 11), (-1, -1), criteria)
            obj_pts.append(objp)
            img_l.append(cl)
            img_r.append(cr)
            print(f'캡처 {len(obj_pts)}')
        elif k == ord('c') and len(obj_pts) >= 10:
            break
        elif k == ord('q'):
            return

    size = (1280, 720)
    print('캘리브레이션 중...')
    _, K1, D1, _, _ = cv2.calibrateCamera(obj_pts, img_l, size, None, None)
    _, K2, D2, _, _ = cv2.calibrateCamera(obj_pts, img_r, size, None, None)
    ret, K1, D1, K2, D2, R, T, _, _ = cv2.stereoCalibrate(
        obj_pts, img_l, img_r, K1, D1, K2, D2, size,
        criteria=criteria, flags=cv2.CALIB_FIX_INTRINSIC)
    print(f'RMS 오차: {ret:.4f}px / 베이스라인: {abs(T[0,0])*1000:.1f}mm')

    R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(
        K1, D1, K2, D2, size, R, T, alpha=0)

    out = os.path.expanduser('~/hri_robot_ws/config/stereo_params.npz')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez(out, K1=K1, D1=D1, K2=K2, D2=D2,
             R=R, T=T.flatten(), R1=R1, R2=R2, P1=P1, P2=P2, Q=Q)
    print(f'저장 완료: {out}')


if __name__ == '__main__':
    main()
