# OmniCalib Open

[English](README.md) | 简体中文

[项目主页](https://hkust-aerial-robotics.github.io/CO-Calib/)

OmniCalib Open 面向任意数量相机，自动完成输入识别、标定板检测、Datawash、ROS1 标准标定 bag 生成和 Kalibr 标定。

用户只需要提供：

- 图像序列、ROS1 bag 或 ROS2 bag
- `rig.yaml`
- `datawash.yaml`
- `target.yaml`
- Detector 和运行设备选择

## 1. 安装

要求：Linux、Conda、Docker。使用 NN-Detector GPU 推理时还需要可用的 NVIDIA 驱动。

```bash
cd Opensource
conda env create -f environment.yml
conda activate omnicalib-open
```

拉取项目发布的 Kalibr 镜像，并设置为工具使用的默认名称：

```bash
docker pull hkustswarm/co-calib:v1.0
docker tag hkustswarm/co-calib:v1.0 omnicalib-kalibr:latest
```

普通用户不需要编译 Kalibr。

## 2. 一键标定

### NN-Detector，使用 GPU

这是推荐运行方式：

```bash
omnicalib run \
  --input /path/to/sequence_or_bag \
  --rig /path/to/rig.yaml \
  --datawash /path/to/datawash.yaml \
  --target /path/to/target.yaml \
  --detector NN-Detector \
  --device gpu
```

如果 CUDA Provider 不可用或初始化失败，程序会自动切换到 CPU 并继续执行，不需要修改命令或重新运行。

也可以直接指定 CPU：

```bash
omnicalib run \
  --input /path/to/sequence_or_bag \
  --rig /path/to/rig.yaml \
  --datawash /path/to/datawash.yaml \
  --target /path/to/target.yaml \
  --detector NN-Detector \
  --device cpu
```

`--device auto` 是默认值，会优先尝试 GPU，然后自动回退 CPU。`NN-Detector` 也是默认 Detector，因此这两个参数都可以省略。

### ACV-Detector

```bash
omnicalib run \
  --input /path/to/sequence_or_bag \
  --rig /path/to/rig.yaml \
  --datawash /path/to/datawash.yaml \
  --target /path/to/target.yaml \
  --detector ACV-Detector \
  --device cpu
```

选择的 Detector 会同时用于 Datawash 和最终标定。ACV-Detector 在 Kalibr 容器中使用 CPU 运行。

默认结果写入输入数据旁的 `<input-name>_omnicalib/`。可使用 `--output /path/to/output` 指定目录；目标目录已经存在时，使用 `--overwrite` 重新生成。

## 3. 输入数据

### 本地快速启动与模型对比

本仓库的 `run_calibration.sh` 默认使用本机 OAK4P 数据、NN-Detector 和 GPU。
`--model` 支持 `eucm-none`（默认）、`ds-none` 和 `omni-radtan`，输出写入
`outputs/<输入序列名>_<模型名>/`。
其他 `omnicalib run` 参数可追加覆盖默认值。
使用 `--input /path/to/sequence` 切换数据集，输出目录自动跟随序列名变化；
传入 `mav0/` 时使用其父目录名。`--output` 可显式指定保存位置。
追加 `--dry-run` 仅打印实际命令，不启动标定。

```bash
./run_calibration.sh \
  --input /mnt/Datasets/VSLAM_benchmark/v0.1/OAK4pNew/Layout_0909/20260909_rig01_cam_static_01_134957_c655e0 \
  --model omni-radtan
```

新数据集首次运行不应传入其他数据集的 `--reuse-datawash` 或 `--detection-cache`。
脚本默认使用仓库的 6×6、0.055 m、0.3 AprilGrid 配置；如实际板不同，请传入 `--target`。


```bash
# 复用之前的 EUCM 选帧结果，仅重新标定 DS 模型
./run_calibration.sh --model ds-none --reuse-datawash outputs/oak4p_135309

# 指定另一处全新输出目录
./run_calibration.sh --model ds-none --reuse-datawash outputs/oak4p_135309 \
  --output outputs/oak4p_ds_comparison_02
```

`--reuse-datawash` 接收已完成运行的根目录（包含 `summary.json`），要求输入、
相机映射、同步容差、检测器和标定板不变，只修改相机模型。复用时不执行 Datawash
筛选，`--datawash` 不会改变已有选帧结果；输出必须是全新目录，不允许覆盖旧结果。
新运行会保留 `datawash/detections_selected.detcache`。旧版本若已删除该缓存，
则从原始图像序列中仅取已选帧补跑 NN 检测，此时需保持原 NN 模型和检测阈值配置。
清洗后的 bag 以只读方式复用，不复制；请保留作为来源的旧运行目录。

如果 Kalibr 失败，但已经保存了选帧角点缓存，可以在全新目录中重试，跳过 NN 检测：

```bash
./run_calibration.sh --model ds-none \
  --reuse-datawash outputs/oak4p_135309 \
  --detection-cache outputs/oak4p_135309_ds-none/datawash/detections_selected.detcache \
  --output outputs/oak4p_135309_ds_retry2
```

指定的缓存会验证 NN 模型哈希、相机 ID 及其时间戳是否与选帧 bag 一致。
新标定自动保存 `kalibr/run.log` 和 `kalibr/command.json`，并启用 Python 故障栈。
如需调试 Kalibr 原生选项，可重复传入 `--kalibr-arg=--选项`；这需要仓库中的
`docker/kalibr/run_calibration.py`，通过只读挂载使用，无需重建镜像。
例如 `--kalibr-arg=--no-final-filtering` 会改变过滤流程，不会默认启用。

工具根据 `--input` 自动识别以下三种格式。

### 图像序列

```text
sequence/
├── cam0/
│   ├── images/
│   │   ├── 000000.png
│   │   └── ...
│   └── timestamps.csv
├── cam1/
│   ├── images/
│   └── timestamps.csv
└── camN/
    ├── images/
    └── timestamps.csv
```

每个相机都需要独立的图像目录和 `timestamps.csv`：

```csv
frame_id,timestamp_ns,filename
0,1700000000000000000,000000.png
1,1700000000100000000,000001.png
```

支持 PNG、JPEG、BMP 和 TIFF。不同相机不要求完全同频，工具按照 `rig.yaml` 中的同步容差形成共视组。

### EuRoC 图像序列

也支持 `mav0/cam0/data.csv` 和 `mav0/cam0/data/` 形式的 EuRoC 数据。
CSV 表头为 `#timestamp [ns],filename`，时间戳按整数纳秒读取。
`--input` 可以指向包含 `mav0/` 的序列根目录，也可以直接指向 `mav0/`；
这两种情况下 `rig.yaml` 的 `directory` 均可填写 `cam0`、`cam1` 等。
输入序列根目录时也支持显式填写 `directory: mav0/cam0`。
原始图像和 CSV 无需转换，`imu0/` 和 `meta/` 不会自动参与标定。

OAK-FFC-4P 四相机可使用 `configs/rig_oak4p_euroc.yaml`（`eucm-none`，同步容差 1 ms）。
若实际板参数为 6×6、标签边长 0.055 m、间距比例 0.3，可使用
`configs/target_aprilgrid_6x6.yaml`；目标配置必须包含 `target_type: aprilgrid`。
EuRoC 读取在宿主机完成，可继续使用原有 `hkustswarm/co-calib:v1.0` 镜像。
加载器仍会一次性读入全部图像字节，请预留足够内存。

### ROS1 bag

将单个 `.bag` 文件传给 `--input`。支持 `sensor_msgs/Image` 和 `sensor_msgs/CompressedImage`。

### ROS2 bag

将包含 `metadata.yaml` 的 rosbag2 目录传给 `--input`。支持 `sensor_msgs/Image` 和 `sensor_msgs/CompressedImage`。

仓库的 `examples/stereo_10frames/` 同时提供图像序列、ROS1 bag 和 ROS2 bag 样例，每个相机包含 10 帧相同数据。

## 4. 配置文件

### rig.yaml

`rig.yaml` 定义相机数量、topic、图像序列目录和相机模型：

```yaml
sync_tolerance_ms: 10.0
cameras:
  - id: cam0
    topic: /camera_0/image_compressed
    model: omni-none
    directory: cam0
    frame_id: camera_0
  - id: cam1
    topic: /camera_1/image_compressed
    model: omni-none
    directory: cam1
    frame_id: camera_1
```

多目系统只需继续增加 `cameras` 项。`id` 和 `topic` 必须唯一，`directory` 必须对应图像序列中的目录。支持：

- `pinhole-radtan`
- `pinhole-equi`
- `pinhole-fov`
- `omni-none`
- `omni-radtan`
- `eucm-none`
- `ds-none`

### datawash.yaml

```yaml
detector_confidence: 0.99
sample_min_detection_points: 12

selection:
  anchor:
    radial_span: 0.25
    iso: 0.50
    budget: 0
  covisible:
    radial_span: 0.00
    iso: 0.30
    budget: 100
  mono_fill:
    radial_span: 0.20
    iso: 0.30
    budget: 0
```

- `detector_confidence`：检测点置信度下限。
- `sample_min_detection_points`：单张图进入选择流程所需的最少有效点数。
- `radial_span`：标定板在有效成像区域中的归一化径向跨度门限。
- `iso`：投影 Jacobian 各向同性门限，越接近 `1` 越严格。
- `budget`：anchor 和 mono fill 按相机限制，covisible 按相机对限制；`0` 表示没有硬上限。

### target.yaml

当前 Detector 面向 6 x 6 AprilGrid：

```yaml
target_type: aprilgrid
tagCols: 6
tagRows: 6
tagSize: 0.055
tagSpacing: 0.3
```

`tagSize` 和 `tagSpacing` 必须与实际打印标定板一致。

仓库提供可直接修改的配置：

- `configs/rig_stereo.yaml`
- `configs/datawash.yaml`
- `configs/target_aprilgrid_6x6.yaml`

## 5. 输出结果

```text
<input-name>_omnicalib/
├── datawash/
│   ├── calibration_clean.bag
│   ├── selected_roles.csv
│   └── summary.json
├── kalibr/
│   ├── calibration-camchain.yaml
│   ├── calibration-results-cam.txt
│   └── calibration-report-cam.pdf
└── summary.json
```

`selected_roles.csv` 记录 anchor、covisible 和 mono fill 的选择结果。`active_cameras` 表示该时刻实际参与标定的相机。

## 6. 外参可视化

`visualization/` 中的浏览器工具用于显示 Kalibr `camchain.yaml` 或 `camchain-imucam.yaml` 中的多相机及相机-IMU 外参。YAML 文件仅在浏览器本地解析，不会上传标定数据。

在 `Opensource/` 仓库根目录创建环境并启动可视化工具：

```bash
cd visualization
conda env create -f environment.yml
conda activate kalibr-visualizer
python -m http.server 8765 --bind 127.0.0.1
```

在浏览器中打开 `http://127.0.0.1:8765/`，然后选择或拖入标定生成的文件：

```text
<input-name>_omnicalib/kalibr/calibration-camchain.yaml
# 或 Kalibr 相机-IMU 标定结果
calibration-camchain-imucam.yaml
```

工具会显示相机视锥、相机坐标轴、相邻相机基线及距离、世界坐标网格和位姿表。如果相机节点包含 `T_cam_imu`，还会显示 IMU 本体、IMU 原生坐标轴、参考相机连线、相对旋转角，以及换算为毫秒的 `timeshift_cam_imu`。工具优先使用 `cam0` 作为 IMU 参考，并支持包含连续 `cam0`、`cam1`、...、`camN` 节点的任意数量相机；`cam0` 之后的每个相机需要提供 4 x 4 `T_cn_cnm1` 变换。

操作方式：

- 左键拖动：旋转视角
- 右键拖动或 Alt + 拖动：平移视角
- 鼠标滚轮：缩放
- `Reset view`：恢复默认视角
- `Fit rig`：将全部相机适配到当前视口

使用 `Ctrl+C` 停止本地服务器。

## 7. 许可证

除非文件或目录另有声明，CO-Calib 自有源代码、文档以及自主开发的
`models/nn_detector_aprilgrid_6x6.onnx` 模型权重，均按照顶层
[`LICENSE`](LICENSE) 中的 BSD-4-Clause 许可证分发。模型的权属与许可范围见
[`models/MODEL_CARD.md`](models/MODEL_CARD.md)。

本仓库在 `vendor/kalibr` 中分发经过修改的 Kalibr。再分发时必须保留原始
Kalibr 版权声明、许可条件、免责声明、广告致谢条款和禁止背书条款。任何提及
本软件功能或用途的广告材料都必须包含以下致谢：

> This product includes software developed by the Autonomous Systems Lab and Skybotix AG.

Kalibr 中的 `incremental_calibration` 和 `incremental_calibration_python`
组件声明使用 LGPLv3，并继续受 LGPLv3 约束。完整分发声明和各组件许可条款见
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)、
[`vendor/kalibr/LICENSE`](vendor/kalibr/LICENSE) 和 [`LICENSES/`](LICENSES/)。
