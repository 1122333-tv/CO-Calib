import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from omnicalib_open.cache import write_cache
from omnicalib_open.config import load_datawash_config
from omnicalib_open.reuse import run_reusing_datawash


class ReuseTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.old = self.root / "old"
        self.old.mkdir()
        self.rig = self.root / "rig.yaml"
        self.rig.write_text(yaml.safe_dump({"cameras": [
            {"id": "cam0", "topic": "/cam0/image_raw", "model": "eucm-none"}]}))
        self.new_rig = self.root / "ds.yaml"
        self.new_rig.write_text(self.rig.read_text().replace("eucm-none", "ds-none"))
        self.target = self.root / "target.yaml"
        self.target.write_text("target_type: aprilgrid\n")
        self.bag = self.old / "selected.bag"
        self.bag.write_bytes(b"original bag must remain unchanged")
        self.model = self.root / "model.onnx"
        self.model.write_bytes(b"test model identity")
        write_cache(self.old / "datawash/detections_selected.detcache", [],
                    model_path=self.model, confidence_threshold=0.99, camera_ids=["cam0"])
        (self.old / "summary.json").write_text(json.dumps({
            "input": str(self.root), "input_type": "sequence", "detector": "nn",
            "rig": str(self.rig), "target": str(self.target),
            "datawash": {"clean_ros1_bag": str(self.bag)}}))
        self.kw = dict(previous=self.old, source=self.root, rig_file=self.new_rig,
                       target_file=self.target, output=self.root / "new", detector="nn",
                       config=load_datawash_config("configs/datawash.yaml"),
                       model_path=self.model, device="gpu", kalibr_image="test-image")

    def test_cached_reuse_changes_only_model_and_output(self):
        before = {p: p.read_bytes() for p in self.old.rglob("*") if p.is_file()}
        with patch("omnicalib_open.orchestrator._run_kalibr") as kalibr, \
                patch("omnicalib_open.reuse.NNDetector") as detector:
            result = run_reusing_datawash(**self.kw)
        detector.assert_not_called()
        self.assertEqual(result["models"], ["ds-none"])
        self.assertFalse(result["rebuilt_selected_detections"])
        self.assertEqual(kalibr.call_args.kwargs["clean_bag"], self.bag)
        self.assertEqual(kalibr.call_args.kwargs["output_dir"], self.root / "new/kalibr")
        self.assertTrue((self.root / "new/datawash/detections_selected.detcache/manifest.json").is_file())
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)

    def test_existing_output_rejected(self):
        self.kw["output"] = self.old
        with self.assertRaises(FileExistsError):
            run_reusing_datawash(**self.kw)

    def test_camera_mapping_change_rejected(self):
        self.new_rig.write_text(self.new_rig.read_text().replace("/cam0/image_raw", "/other"))
        with self.assertRaisesRegex(ValueError, "Only camera models"):
            run_reusing_datawash(**self.kw)

    def test_explicit_cache_is_checked_against_selected_bag(self):
        from omnicalib_open.models import FrameRecord
        self.kw["detection_cache"] = self.old / "datawash/detections_selected.detcache"
        with patch("omnicalib_open.reuse.read_bag", return_value={
                "cam0": [FrameRecord("cam0", 0, 123, b"", "png")]}):
            with self.assertRaisesRegex(ValueError, "do not match the selected bag"):
                run_reusing_datawash(**self.kw)

    def test_explicit_missing_cache_rejected(self):
        self.kw["detection_cache"] = self.root / "missing"
        with self.assertRaisesRegex(ValueError, "existing cache directory"):
            run_reusing_datawash(**self.kw)


if __name__ == "__main__":
    unittest.main()
