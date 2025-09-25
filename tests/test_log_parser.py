import unittest
import os
import numpy as np
import tempfile
import shutil

# Add src to path to allow for imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.log_parser import parse_ptn_file

class TestLogParser(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ptn_file_path = os.path.join(self.test_dir, "test.ptn")
        # Create a dummy binary .ptn file
        # The data should be a 1D array of uint16s with a size that is a multiple of 8
        dummy_data = np.arange(64, dtype='>u2') # 64 is a multiple of 8
        dummy_data.tofile(self.ptn_file_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ptn_file_path = os.path.join(self.test_dir, "test.ptn")
        # Raw data: x=10, y=20, dose1=5 for first record
        # x=18, y=28, dose1=13 for second record
        dummy_data = np.array([10, 20, 0, 0, 5, 0, 0, 0,
                               18, 28, 0, 0, 13, 0, 0, 0], dtype='>u2')
        dummy_data.tofile(self.ptn_file_path)

        self.config = {
            'XPOSGAIN': 0.5,
            'YPOSGAIN': 2.0,
            'XPOSOFFSET': 2.0,
            'YPOSOFFSET': 4.0,
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_parse_ptn_file_smoke(self):
        """
        A simple smoke test to see if the function runs without crashing.
        """
        self.assertTrue(os.path.exists(self.ptn_file_path), "Test file does not exist")
        data = parse_ptn_file(self.ptn_file_path, self.config)
        self.assertIsInstance(data, dict)

    def test_parse_ptn_file_keys(self):
        """
        Test that the parsed data dictionary contains the expected keys.
        """
        data = parse_ptn_file(self.ptn_file_path, self.config)
        self.assertIn("x", data)
        self.assertIn("y", data)
        self.assertIn("mu", data)

    def test_parse_ptn_file_data_shape(self):
        """
        Test that the data arrays have the same length.
        """
        data = parse_ptn_file(self.ptn_file_path, self.config)
        self.assertEqual(data["x"].shape, data["y"].shape)
        self.assertEqual(data["x"].shape, data["mu"].shape)

    def test_parse_ptn_file_data_type(self):
        """
        Test that the data arrays are numpy arrays.
        """
        data = parse_ptn_file(self.ptn_file_path, self.config)
        self.assertIsInstance(data["x"], np.ndarray)
        self.assertIsInstance(data["y"], np.ndarray)
        self.assertIsInstance(data["mu"], np.ndarray)

    def test_coordinate_transformation(self):
        """
        Test that the coordinate transformation is applied correctly.
        """
        data = parse_ptn_file(self.ptn_file_path, self.config)

        # Expected values based on the formula:
        # real_x = (raw_x - XPOSOFFSET) * XPOSGAIN
        # real_y = (raw_y - YPOSOFFSET) * YPOSGAIN

        # First record:
        # x = (10 - 2.0) * 0.5 = 4.0
        # y = (20 - 4.0) * 2.0 = 32.0
        # mu = 5

        # Second record:
        # x = (18 - 2.0) * 0.5 = 8.0
        # y = (28 - 4.0) * 2.0 = 48.0
        # mu = 5 + 13 = 18

        expected_x = np.array([4.0, 8.0])
        expected_y = np.array([32.0, 48.0])
        expected_mu = np.array([5, 18])

        np.testing.assert_allclose(data['x'], expected_x)
        np.testing.assert_allclose(data['y'], expected_y)
        np.testing.assert_allclose(data['mu'], expected_mu)


if __name__ == '__main__':
    unittest.main()
