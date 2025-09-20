import unittest
import os
import numpy as np

# Add src to path to allow for imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.dicom_parser import parse_dcm_file

class TestDicomParser(unittest.TestCase):

    def setUp(self):
        # This path is relative to the root of the repository
        self.dcm_file_path = "Data_ex/RP.1.2.840.113854.241506614174277151614979936366782948539.1.dcm"

    def test_parse_dcm_file_smoke(self):
        """
        A simple smoke test to see if the function runs without crashing.
        """
        self.assertTrue(os.path.exists(self.dcm_file_path), "Test file does not exist")
        data = parse_dcm_file(self.dcm_file_path)
        self.assertIsInstance(data, dict)

    def test_parse_dcm_file_structure(self):
        """
        Test that the parsed data dictionary has the expected structure.
        """
        data = parse_dcm_file(self.dcm_file_path)
        self.assertIn("beams", data)
        self.assertIsInstance(data["beams"], dict)

        # Check a sample beam
        # Note: The beam name might vary, so we just get the first one
        first_beam_name = list(data["beams"].keys())[0]
        beam_data = data["beams"][first_beam_name]

        self.assertIn("layers", beam_data)
        self.assertIsInstance(beam_data["layers"], dict)

        # Check a sample layer
        first_layer_index = list(beam_data["layers"].keys())[0]
        layer_data = beam_data["layers"][first_layer_index]

        self.assertIn("positions", layer_data)
        self.assertIn("mu", layer_data)
        self.assertIn("cumulative_mu", layer_data)

        self.assertIsInstance(layer_data["positions"], np.ndarray)
        self.assertIsInstance(layer_data["mu"], np.ndarray)
        self.assertIsInstance(layer_data["cumulative_mu"], np.ndarray)

        # Check that positions has 2 columns (x, y)
        self.assertEqual(layer_data["positions"].shape[1], 2)

        # Check that mu and positions have the same number of entries
        self.assertEqual(layer_data["positions"].shape[0], layer_data["mu"].shape[0])


if __name__ == '__main__':
    unittest.main()
