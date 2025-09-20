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

if __name__ == '__main__':
    unittest.main()
