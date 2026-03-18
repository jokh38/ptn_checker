import unittest
import os
import numpy as np
import tempfile
import shutil

from tests.conftest import create_dummy_dcm_file
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
            dummy_ptn_data[i * 8 + 7] = 50000  # beam_on_off > 49152 threshold for Beam On
        dummy_ptn_data.tofile(self.ptn_file_path)

        # Create dummy DICOM file
        self.dcm_file_path = os.path.join(self.test_dir, "test.dcm")
        create_dummy_dcm_file(self.dcm_file_path)

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
