import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from omnicalib_open.orchestrator import _run_kalibr


class KalibrRunnerTests(unittest.TestCase):
    def test_extra_arguments_logs_and_readonly_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process = MagicMock()
            process.__enter__.return_value = process
            process.stdout = iter(["Calibration complete.\n"])
            process.wait.return_value = 0
            with patch("omnicalib_open.orchestrator.subprocess.Popen", return_value=process):
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
