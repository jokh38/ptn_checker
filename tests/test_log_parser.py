import unittest
import os
import numpy as np

# Add src to path to allow for imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.log_parser import parse_ptn_file

class TestLogParser(unittest.TestCase):

    def setUp(self):
        # This path is relative to the root of the repository
        self.ptn_file_path = "Data_ex/2025042401440800/02_0014046_001_002_001.ptn"

    def test_parse_ptn_file_smoke(self):
        """
        A simple smoke test to see if the function runs without crashing.
        """
        self.assertTrue(os.path.exists(self.ptn_file_path), "Test file does not exist")
        data = parse_ptn_file(self.ptn_file_path)
        self.assertIsInstance(data, dict)

    def test_parse_ptn_file_keys(self):
        """
        Test that the parsed data dictionary contains the expected keys.
        """
        data = parse_ptn_file(self.ptn_file_path)
        self.assertIn("x", data)
        self.assertIn("y", data)
        self.assertIn("mu", data)

    def test_parse_ptn_file_data_shape(self):
        """
        Test that the data arrays have the same length.
        """
        data = parse_ptn_file(self.ptn_file_path)
        self.assertEqual(data["x"].shape, data["y"].shape)
        self.assertEqual(data["x"].shape, data["mu"].shape)

    def test_parse_ptn_file_data_type(self):
        """
        Test that the data arrays are numpy arrays.
        """
        data = parse_ptn_file(self.ptn_file_path)
        self.assertIsInstance(data["x"], np.ndarray)
        self.assertIsInstance(data["y"], np.ndarray)
        self.assertIsInstance(data["mu"], np.ndarray)

    def test_calibration_logic(self):
        """
        Test that the calibration logic is applied correctly.
        """
        config_params = {
            'TIMEGAIN': 0.1,
            'XPOSOFFSET': 100.0,
            'YPOSOFFSET': 200.0,
            'XPOSGAIN': 0.5,
            'YPOSGAIN': 0.25
        }

        data = parse_ptn_file(self.ptn_file_path, config_params)

        # Check for new keys
        self.assertIn("x_mm", data)
        self.assertIn("y_mm", data)
        self.assertIn("x_raw", data) # Check for original raw data too
        self.assertIn("y_raw", data)


        # Manually calibrate the first data point to verify
        raw_x_first = data["x_raw"][0]
        raw_y_first = data["y_raw"][0]

        expected_x_mm_first = (raw_x_first - config_params['XPOSOFFSET']) * config_params['XPOSGAIN']
        expected_y_mm_first = (raw_y_first - config_params['YPOSOFFSET']) * config_params['YPOSGAIN']

        self.assertAlmostEqual(data["x_mm"][0], expected_x_mm_first, places=5)
        self.assertAlmostEqual(data["y_mm"][0], expected_y_mm_first, places=5)


if __name__ == '__main__':
    unittest.main()
