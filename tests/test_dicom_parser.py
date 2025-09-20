import unittest
import os
import numpy as np
import pydicom

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


    def test_parsed_data_types(self):
        """
        Test that the parsed numpy arrays have the correct float32 data type.
        """
        data = parse_dcm_file(self.dcm_file_path)
        first_beam_name = list(data["beams"].keys())[0]
        beam_data = data["beams"][first_beam_name]
        first_layer_index = list(beam_data["layers"].keys())[0]
        layer_data = beam_data["layers"][first_layer_index]

        # The 'mu' array is calculated from weights, so we can't directly test its dtype
        # from the frombuffer change yet. We will test the intermediate 'weights' array
        # after refactoring. For now, we focus on 'positions' which will be directly affected.
        # However, to follow TDD, we can check the 'mu' dtype as well, which will also fail.
        self.assertEqual(layer_data["positions"].dtype, np.float32)
        self.assertEqual(layer_data["mu"].dtype, np.float32)


    def test_invalid_dicom_file(self):
        """
        Test that an InvalidDicomError is raised for a non-DICOM file.
        """
        # Create a dummy non-DICOM file
        invalid_file = "invalid.dcm"
        with open(invalid_file, "w") as f:
            f.write("this is not a dicom file")

        with self.assertRaises(pydicom.errors.InvalidDicomError):
            parse_dcm_file(invalid_file)

        os.remove(invalid_file)


    def test_missing_attribute(self):
        """
        Test that the parser handles DICOM files with missing attributes gracefully.
        """
        # Create a dummy DICOM dataset with a missing attribute
        file_meta = pydicom.dataset.FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.481.5' # RT Plan Storage
        file_meta.MediaStorageSOPInstanceUID = "1.2.3"
        file_meta.ImplementationClassUID = "1.2.3.4"

        ds = pydicom.dataset.FileDataset("test.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
        ds.IonBeamSequence = [pydicom.dataset.Dataset()] # Add a beam without IonControlPointSequence

        # Give the beam a name so the parser can try to process it
        ds.IonBeamSequence[0].BeamName = "TestBeam"
        ds.IonBeamSequence[0].BeamDescription = "TestDescription"


        temp_dcm_file = "temp_missing_attr.dcm"
        ds.save_as(temp_dcm_file, write_like_original=False)

        try:
            # The parser should run without raising an unhandled exception
            data = parse_dcm_file(temp_dcm_file)
            # It should return a valid dictionary, and the faulty beam should be skipped
            self.assertIn("beams", data)
            self.assertNotIn("TestBeam", data["beams"])
        finally:
            os.remove(temp_dcm_file)


if __name__ == '__main__':
    unittest.main()
