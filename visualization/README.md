# Kalibr Camera / IMU Visualizer

English | [简体中文](README.zh-CN.md)

A dependency-free browser visualizer for Kalibr multi-camera and camera-IMU extrinsics. YAML files are parsed locally and are never uploaded.

## Environment and startup

```bash
conda env create -f environment.yml
conda activate kalibr-visualizer
python -m http.server 8765
```

Open `http://127.0.0.1:8765/` in a browser.

Python is only used to serve the static files. The visualizer has no third-party Python dependencies.

## Input

Select or drop a Kalibr `camchain.yaml` or `camchain-imucam.yaml`. The file must contain contiguous `cam0`, `cam1`, ... nodes. Every camera after `cam0` must provide a 4x4 `T_cn_cnm1`.

Camera-IMU visualization is enabled automatically when one or more camera nodes provide a 4x4 `T_cam_imu`. The reference node's optional `timeshift_cam_imu`, expressed in seconds by Kalibr, is shown in milliseconds. The visualizer uses `cam0` as the IMU reference when available, or otherwise the first node containing `T_cam_imu`. Both inline and block-style YAML matrix encodings are supported.

## Coordinate transforms

Transform names follow `T_A_B`: the matrix maps points from frame B to frame A.

```text
T_ci_c0 = T_ci_ci-1 * ... * T_c1_c0
T_c0_ci = inverse(T_ci_c0)
T_W_ci  = T_W_c0 * T_c0_ci
T_W_imu = T_W_cref * T_cref_imu

T_W_c0 = [0 0 1 0]
         [1 0 0 0]
         [0 1 0 0]
         [0 0 0 1]
```

The world frame uses X forward, Y left, and Z up. After transforming all cameras into the world frame, one common XY translation moves the origin to the mean XY position of all camera centers. Z coordinates, orientations, and relative camera positions remain unchanged.

Here, `cref` is the camera node that contains `T_cam_imu`; the matrix maps IMU-frame points into that camera frame. Camera frustums use the original optical axes. Only the displayed camera axis arrows use this mapping:

```text
X_display = -X_optical
Y_display = -Y_optical
Z_display =  Z_optical
```

The IMU arrows display its native X, Y, and Z axes without the camera optical-axis mapping. The pose table reports the IMU distance and rotation relative to its reference camera, together with `timeshift_cam_imu`.

## Controls

- Left drag: orbit
- Right drag or Alt + drag: pan
- Mouse wheel: zoom
