import unittest
import os
import numpy as np
import tempfile
import shutil
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ImplicitVRLittleEndian

# Add src to path to allow for imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.dicom_parser import parse_dcm_file

class TestDicomParser(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dcm_file_path = os.path.join(self.test_dir, "test.dcm")
        self.create_dummy_dcm_file(self.dcm_file_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def create_dummy_dcm_file(self, filepath):
        """Creates a dummy DICOM file for testing."""
        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.481.5'
        file_meta.MediaStorageSOPInstanceUID = "1.2.3"
        file_meta.ImplementationClassUID = "1.2.3.4"
        file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

        ds = Dataset()
        ds.PatientName = "Test^Patient"
        ds.PatientID = "123456"

        beam_sequence = Dataset()
        beam_sequence.BeamName = "TestBeam"

        # Create first control point
        cp1 = Dataset()
        cp1.ControlPointIndex = '0'
        cp1.GantryAngle = 0
        cp1.CumulativeMetersetWeight = 0.0
        bld_sequence1 = Dataset()
        bld_sequence1.RTBeamLimitingDeviceType = 'MLCX'
        bld_sequence1.LeafJawPositions = [str(i) for i in range(120)]
        cp1.BeamLimitingDevicePositionSequence = [bld_sequence1]
        cp1.add_new((0x300b, 0x1094), 'OB', b'\x00' * 8 * 10)
        cp1.add_new((0x300b, 0x1096), 'OB', b'\x00' * 4 * 10)

        # Create second control point
        cp2 = Dataset()
        cp2.ControlPointIndex = '1'
        cp2.GantryAngle = 0
        cp2.CumulativeMetersetWeight = 10.0
        bld_sequence2 = Dataset()
        bld_sequence2.RTBeamLimitingDeviceType = 'MLCX'
        bld_sequence2.LeafJawPositions = [str(i) for i in range(120)]
        cp2.BeamLimitingDevicePositionSequence = [bld_sequence2]
        cp2.add_new((0x300b, 0x1094), 'OB', b'\x00' * 8 * 10)
        cp2.add_new((0x300b, 0x1096), 'OB', b'\x00' * 4 * 10)

        beam_sequence.ControlPointSequence = [cp1, cp2]
        ds.BeamSequence = [beam_sequence]

        ds.file_meta = file_meta
        ds.is_little_endian = True
        ds.is_implicit_VR = True
        ds.save_as(filepath, write_like_original=False)

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

        self.assertIn("TestBeam", data["beams"])
        beam_data = data["beams"]["TestBeam"]

        self.assertIn("layers", beam_data)
        self.assertIsInstance(beam_data["layers"], dict)

        self.assertIn(0, beam_data["layers"])
        layer_data = beam_data["layers"][0]

        self.assertIn("positions", layer_data)
        self.assertIn("mu", layer_data)
        self.assertIn("cumulative_mu", layer_data)

        self.assertIsInstance(layer_data["positions"], np.ndarray)
        self.assertIsInstance(layer_data["mu"], np.ndarray)
        self.assertIsInstance(layer_data["cumulative_mu"], np.ndarray)

        self.assertEqual(layer_data["positions"].shape[1], 2)
        self.assertEqual(layer_data["positions"].shape[0], layer_data["mu"].shape[0])


if __name__ == '__main__':
    unittest.main()
