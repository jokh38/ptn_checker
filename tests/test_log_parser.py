import unittest
import os
import numpy as np
import tempfile
import shutil

from src.log_parser import parse_ptn_file


class TestCorrectLogParser(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ptn_file_path = os.path.join(self.test_dir, "test.ptn")

        # Create a dummy binary .ptn file with 2 records (16 shorts)
        # Data format: x_raw, y_raw, x_size_raw, y_size_raw, dose1, dose2, layer, beam_on_off
        # Beam On threshold: beam_on_off > 2**15 + 2**14 = 49152, so use 50000 for On
        self.raw_data = np.array([
            1000, 2000, 300, 400, 50, 60, 1, 50000,
            1010, 2020, 310, 410, 55, 65, 1, 50000
        ], dtype='>u2')
        self.raw_data.tofile(self.ptn_file_path)

        # Full config parameters from the "correct" parser
        self.config = {
            'TIMEGAIN': 10.0,
            'XPOSOFFSET': 500.0,
            'YPOSOFFSET': 1500.0,
            'XPOSGAIN': 0.1,
            'YPOSGAIN': 0.2
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_parse_ptn_file_returns_comprehensive_dict(self):
        """
        Test that the parser returns all expected keys and values with correct transformations.
        This test is designed for the NEW, correct parser logic.
        """
        # This will fail with the current src/log_parser.py
        data = parse_ptn_file(self.ptn_file_path, self.config)

        # 1. Check for all expected keys
        expected_keys = [
            "time_ms", "x_raw", "y_raw", "x_size_raw", "y_size_raw",
            "dose1_au", "dose2_au", "layer_num", "beam_on_off",
            "x_mm", "y_mm", "x_size_mm", "y_size_mm"
        ]
        for key in expected_keys:
            self.assertIn(key, data, f"Key '{key}' is missing from the output dictionary.")

        # 2. Check data types and shapes
        self.assertEqual(data['time_ms'].shape[0], 2)
        self.assertEqual(data['x_mm'].shape[0], 2)
        self.assertIsInstance(data['x_mm'], np.ndarray)

        # 3. Check calculated values
        # Time = index * TIMEGAIN
        expected_time = np.array([0.0, 10.0])
        np.testing.assert_allclose(data['time_ms'], expected_time, rtol=1e-6)

        # x_mm = (raw_x - XPOSOFFSET) * XPOSGAIN
        # y_mm = (raw_y - YPOSOFFSET) * YPOSGAIN
        expected_x_mm = np.array([(1000 - 500.0) * 0.1, (1010 - 500.0) * 0.1]) # [50.0, 51.0]
        expected_y_mm = np.array([(2000 - 1500.0) * 0.2, (2020 - 1500.0) * 0.2]) # [100.0, 104.0]
        np.testing.assert_allclose(data['x_mm'], expected_x_mm, rtol=1e-6)
        np.testing.assert_allclose(data['y_mm'], expected_y_mm, rtol=1e-6)

        # x_size_mm = raw_x_size * XPOSGAIN
        # y_size_mm = raw_y_size * YPOSGAIN
        expected_x_size_mm = np.array([300 * 0.1, 310 * 0.1]) # [30.0, 31.0]
        expected_y_size_mm = np.array([400 * 0.2, 410 * 0.2]) # [80.0, 82.0]
        np.testing.assert_allclose(data['x_size_mm'], expected_x_size_mm, rtol=1e-6)
        np.testing.assert_allclose(data['y_size_mm'], expected_y_size_mm, rtol=1e-6)

    def test_non_multiple_of_8_file(self):
        """Test that a file with data not a multiple of 8 shorts raises ValueError."""
        bad_file = os.path.join(self.test_dir, "bad.ptn")
        # 7 shorts - not a multiple of 8
        bad_data = np.array([1, 2, 3, 4, 5, 6, 7], dtype='>u2')
        bad_data.tofile(bad_file)
        with self.assertRaises(ValueError):
            parse_ptn_file(bad_file, self.config)

    def test_missing_config_key(self):
        """Test that missing essential config keys raise KeyError."""
        incomplete_config = {
            'TIMEGAIN': 10.0,
            'XPOSOFFSET': 500.0,
            # Missing YPOSOFFSET, XPOSGAIN, YPOSGAIN
        }
        with self.assertRaises(KeyError):
            parse_ptn_file(self.ptn_file_path, incomplete_config)

    def test_nonexistent_file(self):
        """Test that a non-existent file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            parse_ptn_file("/nonexistent/path/file.ptn", self.config)


if __name__ == '__main__':
    unittest.main()
