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

        # Create dummy PTN file with proper beam_on_off values
        self.ptn_file_path = os.path.join(self.test_dir, "test.ptn")
        # 10 spots * 8 shorts/spot = 80 shorts
        # Data format: x_raw, y_raw, x_size_raw, y_size_raw, dose1, dose2, layer, beam_on_off
        dummy_ptn_data = np.arange(80, dtype='>u2')
        # Set beam_on_off values to 1 (positions 7, 15, 23, 31, 39, 47, 55, 63, 71, 79)
        for i in range(10):
            dummy_ptn_data[i * 8 + 7] = 1  # beam_on_off = 1 for all spots
        dummy_ptn_data.tofile(self.ptn_file_path)

        # Create dummy DICOM file
        self.dcm_file_path = os.path.join(self.test_dir, "test.dcm")
        self.create_dummy_dcm_file(self.dcm_file_path)

        self.config = {
            'XPOSGAIN': 1.0, 'YPOSGAIN': 1.0,
            'XPOSOFFSET': 0.0, 'YPOSOFFSET': 0.0,
            'TIMEGAIN': 0.001
        }
        self.log_data = parse_ptn_file(self.ptn_file_path, self.config)
        plan_data = parse_dcm_file(self.dcm_file_path)
        self.plan_layer = plan_data['beams'][1]['layers'][0]


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

        ion_beam_sequence = Dataset()
        ion_beam_sequence.TreatmentMachineName = "TestMachine"
        ion_beam_sequence.BeamNumber = 1

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

        ion_beam_sequence.IonControlPointSequence = [cp1, cp2]
        ds.IonBeamSequence = [ion_beam_sequence]

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
        self.assertIn('mean_diff_x', results)
        self.assertIn('mean_diff_y', results)
        self.assertIn('std_diff_x', results)
        self.assertIn('std_diff_y', results)

    def test_calculate_differences_data_shape(self):
        """
        Test that the difference arrays have the correct shape.
        """
        self.plan_layer['positions'] = np.zeros((10, 2))
        self.plan_layer['mu'] = np.zeros(10)
        results = calculate_differences_for_layer(self.plan_layer, self.log_data)
        self.assertEqual(results['log_positions'].shape[0], self.log_data['x_mm'].shape[0])
        self.assertIsInstance(results['mean_diff_x'], (float, np.floating))

    def test_result_structure(self):
        """
        Test that the results have the expected structure.
        """
        self.plan_layer['positions'] = np.zeros((10, 2))
        self.plan_layer['mu'] = np.zeros(10)
        results = calculate_differences_for_layer(self.plan_layer, self.log_data)
        self.assertIn('plan_positions', results)
        self.assertIn('log_positions', results)
        self.assertIsInstance(results['std_diff_x'], (float, np.floating))
        self.assertIsInstance(results['std_diff_y'], (float, np.floating))

if __name__ == '__main__':
    unittest.main()
