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

if __name__ == '__main__':
    unittest.main()
