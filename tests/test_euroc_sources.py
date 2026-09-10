import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from omnicalib_open.models import CameraSpec, RigSpec
from omnicalib_open.sources import _read_timestamp_rows, decode_frame, load_frame_groups


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_camera(self, directory, euroc=True):
        images = directory / ("data" if euroc else "images")
        images.mkdir(parents=True)
        cv2.imwrite(str(images / "frame.png"), np.zeros((8, 12), dtype=np.uint8))
        header = "\ufeff#timestamp [ns], filename\r\n" if euroc else "frame_id,timestamp_ns,filename\n"
        row = "1788932997598470801,frame.png\n" if euroc else "42,1788932997598470801,frame.png\n"
        (directory / ("data.csv" if euroc else "timestamps.csv")).write_text(header + row)

    def rig(self, directory="cam0"):
        return RigSpec((CameraSpec("cam0", "/cam0/image_raw", directory, "cam0"),), 1000000)

    def test_euroc_roots_and_explicit_directory(self):
        self.write_camera(self.root / "mav0" / "cam0")
        for root, directory in ((self.root, "cam0"), (self.root / "mav0", "cam0"),
                                (self.root, "mav0/cam0")):
            with self.subTest(root=root, directory=directory):
                groups = load_frame_groups(root, self.rig(directory))
                self.assertEqual(len(groups), 1)
                frame = groups[0].frames["cam0"]
                self.assertEqual(frame.timestamp_ns, 1788932997598470801)
                self.assertEqual(frame.source_index, 0)
                self.assertEqual(decode_frame(frame).shape, (8, 12, 3))

    def test_original_sequence(self):
        self.write_camera(self.root / "cam0", euroc=False)
        frame = load_frame_groups(self.root, self.rig())[0].frames["cam0"]
        self.assertEqual(frame.source_index, 42)
        self.assertEqual(frame.timestamp_ns, 1788932997598470801)

    def test_missing_image(self):
        directory = self.root / "cam0"
        self.write_camera(directory)
        (directory / "data" / "frame.png").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "data.csv"):
            _read_timestamp_rows(directory)

    def test_invalid_header_and_empty_csv(self):
        directory = self.root / "cam0"
        self.write_camera(directory)
        for content, error in (("timestamp,filename\n1,frame.png\n", "requires columns"),
                               ("#timestamp [ns],filename\n", "No frames")):
            with self.subTest(content=content):
                (directory / "data.csv").write_text(content)
                with self.assertRaisesRegex(ValueError, error):
                    _read_timestamp_rows(directory)


if __name__ == "__main__":
    unittest.main()
