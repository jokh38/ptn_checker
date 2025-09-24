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

from src.log_parser import parse_ptn_file
from src.dicom_parser import parse_dcm_file
from src.calculator import calculate_differences_for_layer

class TestCalculator(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

        # Create dummy PTN file
        self.ptn_file_path = os.path.join(self.test_dir, "test.ptn")
        # 10 spots * 8 shorts/spot = 80 shorts
        dummy_ptn_data = np.arange(80, dtype='>u2')
        dummy_ptn_data.tofile(self.ptn_file_path)

        # Create dummy DICOM file
        self.dcm_file_path = os.path.join(self.test_dir, "test.dcm")
        self.create_dummy_dcm_file(self.dcm_file_path)

        self.log_data = parse_ptn_file(self.ptn_file_path)
        plan_data = parse_dcm_file(self.dcm_file_path)
        self.plan_layer = plan_data['beams']['TestBeam']['layers'][0]


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

    def test_calculate_differences_smoke(self):
        """
        A simple smoke test to see if the function runs without crashing.
        """
        self.plan_layer['positions'] = np.zeros((10, 2))
        self.plan_layer['mu'] = np.zeros(10)

        results = calculate_differences_for_layer(self.plan_layer, self.log_data)
        self.assertIsInstance(results, dict)

    def test_calculate_differences_keys(self):
        """
        Test that the results dictionary contains the expected keys.
        """
        self.plan_layer['positions'] = np.zeros((10, 2))
        self.plan_layer['mu'] = np.zeros(10)
        results = calculate_differences_for_layer(self.plan_layer, self.log_data)
        self.assertIn('diff_x', results)
        self.assertIn('diff_y', results)
        self.assertIn('hist_fit_x', results)
        self.assertIn('hist_fit_y', results)

    def test_calculate_differences_data_shape(self):
        """
        Test that the difference arrays have the correct shape.
        """
        self.plan_layer['positions'] = np.zeros((10, 2))
        self.plan_layer['mu'] = np.zeros(10)
        results = calculate_differences_for_layer(self.plan_layer, self.log_data)
        self.assertEqual(results['diff_x'].shape, self.log_data['x'].shape)
        self.assertEqual(results['diff_y'].shape, self.log_data['y'].shape)

    def test_hist_fit_results(self):
        """
        Test that the histogram fit results have the expected keys.
        """
        self.plan_layer['positions'] = np.zeros((10, 2))
        self.plan_layer['mu'] = np.zeros(10)
        results = calculate_differences_for_layer(self.plan_layer, self.log_data)
        fit_results_x = results['hist_fit_x']
        self.assertIn('amplitude', fit_results_x)
        self.assertIn('mean', fit_results_x)
        self.assertIn('stddev', fit_results_x)

        fit_results_y = results['hist_fit_y']
        self.assertIn('amplitude', fit_results_y)
        self.assertIn('mean', fit_results_y)
        self.assertIn('stddev', fit_results_y)

if __name__ == '__main__':
    unittest.main()
