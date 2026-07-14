#!/usr/bin/env python3
"""
calibrate_cam_to_robot.py
카메라 좌표계 -> Piper 로봇 base 좌표계 변환행렬(4x4) 계산

원리: 같은 점을 두 좌표계에서 측정한 대응쌍 4개 이상으로
      SVD 기반 강체변환(Kabsch) 추정

절차 (점 1개당):
  1. 작업 공간에 마커(작은 물체)를 놓는다
  2. 카메라 화면에서 마커를 클릭 -> 뎁스로 카메라 좌표 자동 계산
  3. Piper를 손으로(티칭 모드) 움직여 end-effector 끝을 마커에 댄다
  4. 엔터 -> 로봇 좌표 자동 기록 (piper_sdk가 없으면 수동 입력)
  5. 4~6개 점 반복 후 's' 키 -> config/cam_to_robot.npy 저장

사용법: python3 calibrate_cam_to_robot.py --device 0
"""
import cv2
import numpy as np
import argparse
import os

PARAM_PATH = os.path.expanduser('~/hri_robot_ws/config/stereo_params.npz')
OUT_PATH   = os.path.expanduser('~/hri_robot_ws/config/cam_to_robot.npy')

clicked = None


def on_mouse(event, x, y, flags, param):
    global clicked
    if event == cv2.EVENT_LBUTTONDOWN:
        clicked = (x, y)


def rigid_transform(A, B):
    """A(카메라) -> B(로봇) 강체변환. A,B: (N,3)"""
    cA, cB = A.mean(0), B.mean(0)
    H = (A - cA).T @ (B - cB)
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1
        R = Vt.T @ U.T
    t = cB - R @ cA
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = R, t
    return T


def get_robot_pos(piper):
    """Piper end-effector 위치 읽기 (미터). SDK 없으면 수동 입력"""
    if piper:
        pose = piper.GetArmEndPoseMsgs().end_pose
        return np.array([pose.X_axis, pose.Y_axis, pose.Z_axis]) * 1e-6
    s = input('  로봇 좌표 x y z (미터, 공백 구분): ')
    return np.array([float(v) for v in s.split()])


def main():
    global clicked
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', type=int, default=0)
    args = ap.parse_args()

    # 내부 파라미터
    if os.path.exists(PARAM_PATH):
        p = np.load(PARAM_PATH)
        fx, fy = p['P1'][0, 0], p['P1'][1, 1]
        cx, cy = p['P1'][0, 2], p['P1'][1, 2]
    else:
        fx = fy = 1024.0
        cx, cy = 640.0, 360.0
        print('경고: stereo_params.npz 없음, 기본 파라미터 사용')

    # piper 연결 시도
    piper = None
    try:
        from piper_sdk import C_PiperInterface_V2
        piper = C_PiperInterface_V2('can0')
        piper.ConnectPort()
        print('Piper 연결됨 - 로봇 좌표 자동 기록')
    except Exception:
        print('piper_sdk 없음 - 로봇 좌표 수동 입력 모드')

    cap = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 2560)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    stereo = cv2.StereoSGBM_create(
        minDisparity=0, numDisparities=128, blockSize=9,
        P1=8 * 81, P2=32 * 81, uniquenessRatio=10)

    cam_pts, rob_pts = [], []
    cv2.namedWindow('calib')
    cv2.setMouseCallback('calib', on_mouse)
    print('마커 클릭 -> 로봇 끝을 마커에 대고 엔터 / s: 저장 / q: 종료')

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        left, right = frame[:, :1280], frame[:, 1280:]

        disp_img = left.copy()
        cv2.putText(disp_img, f'points: {len(cam_pts)} (need >= 4)',
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow('calib', disp_img)
        k = cv2.waitKey(1) & 0xFF

        if clicked is not None:
            u, v = clicked
            clicked = None
            gl = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
            gr = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)
            d = stereo.compute(gl, gr).astype(np.float32) / 16.0
            patch = d[max(0, v-3):v+4, max(0, u-3):u+4]
            valid = patch[patch > 0]
            if valid.size < 5:
                print('  뎁스 없음 - 다시 클릭')
                continue
            disp_v = np.median(valid)
            B = 0.120 if not os.path.exists(PARAM_PATH) \
                else abs(np.load(PARAM_PATH)['T'][0])
            z = fx * B / disp_v
            x = (u - cx) * z / fx
            y = (v - cy) * z / fy
            print(f'  카메라 좌표: ({x:.3f}, {y:.3f}, {z:.3f})')
            print('  로봇 끝을 마커에 대고 엔터...')
            input()
            rp = get_robot_pos(piper)
            cam_pts.append([x, y, z])
            rob_pts.append(rp)
            print(f'  점 {len(cam_pts)} 기록: 로봇 {np.round(rp, 3)}')

        if k == ord('s') and len(cam_pts) >= 4:
            T = rigid_transform(np.array(cam_pts), np.array(rob_pts))
            err = np.linalg.norm(
                (T @ np.c_[cam_pts, np.ones(len(cam_pts))].T)[:3].T
                - np.array(rob_pts), axis=1)
            print(f'평균 오차: {err.mean()*1000:.1f}mm')
            os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
            np.save(OUT_PATH, T)
            print(f'저장 완료: {OUT_PATH}')
            break
        elif k == ord('q'):
            break


if __name__ == '__main__':
    main()
