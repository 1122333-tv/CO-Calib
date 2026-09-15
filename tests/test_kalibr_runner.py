import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from omnicalib_open.orchestrator import _require_camera_messages, _run_kalibr


class KalibrRunnerTests(unittest.TestCase):
    def test_extra_arguments_logs_and_readonly_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process = MagicMock()
            process.__enter__.return_value = process
            process.stdout = iter(["Calibration complete.\n"])
            process.wait.return_value = 0
            with patch("omnicalib_open.orchestrator._require_camera_messages"), \
                    patch("omnicalib_open.orchestrator.subprocess.Popen", return_value=process):
                _run_kalibr(detector="nn", clean_bag=root / "input.bag",
                            selected_cache=root / "cache", rig_path=root / "rig.yaml",
                            target_path=root / "target.yaml", output_dir=root / "output",
                            docker_image="test-image", kalibr_args=["--no-final-filtering"])
            command = json.loads((root / "output/command.json").read_text())
            self.assertEqual(command[-2:], ["--", "--no-final-filtering"])
            self.assertIn(str(root / "input.bag") + ":/output/calibration.bag:ro", command)
            self.assertTrue(any("run_calibration.py:/usr/local/bin/omnicalib-calibrate:ro" in item
                                for item in command))
            self.assertEqual((root / "output/run.log").read_text(), "Calibration complete.\n")

    def test_missing_and_empty_connections_stop_before_docker(self):
        from rosbags.rosbag1 import Writer
        from rosbags.typesys import Stores, get_typestore

        for include_empty_connection in (False, True):
            with self.subTest(empty_connection=include_empty_connection), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                rig = root / "rig.yaml"
                rig.write_text("cameras:\n"
                               "  - {id: cam0, topic: /cam0/image_raw, model: eucm-none}\n"
                               "  - {id: cam1, topic: /cam1/image_raw, model: eucm-none}\n")
                bag = root / "input.bag"
                with Writer(bag) as writer:
                    store = get_typestore(Stores.ROS1_NOETIC)
                    if include_empty_connection:
                        writer.add_connection("/cam0/image_raw", "sensor_msgs/msg/Image", typestore=store)
                    connection = writer.add_connection("/cam1/image_raw", "sensor_msgs/msg/Image", typestore=store)
                    writer.write(connection, 1, b"unused payload")
                with patch("omnicalib_open.orchestrator.subprocess.Popen") as launch:
                    with self.assertRaisesRegex(ValueError, r"no image messages for cam0"):
                        _run_kalibr(detector="nn", clean_bag=bag, selected_cache=root / "cache",
                                    rig_path=rig, target_path=root / "target.yaml",
                                    output_dir=root / "output", docker_image="test-image")
                    launch.assert_not_called()
                self.assertFalse((root / "output").exists())

    def test_nonempty_camera_passes_preflight(self):
        from rosbags.rosbag1 import Writer
        from rosbags.typesys import Stores, get_typestore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rig = root / "rig.yaml"
            rig.write_text("cameras:\n  - {id: cam0, topic: /cam0/image_raw, model: eucm-none}\n")
            bag = root / "input.bag"
            with Writer(bag) as writer:
                connection = writer.add_connection("/cam0/image_raw", "sensor_msgs/msg/Image",
                                                   typestore=get_typestore(Stores.ROS1_NOETIC))
                writer.write(connection, 1, b"unused payload")
            _require_camera_messages(bag, rig)
