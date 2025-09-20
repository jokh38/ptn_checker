import unittest
import os
import numpy as np

# Add src to path to allow for imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.log_parser import parse_ptn_file
from src.dicom_parser import parse_dcm_file
from src.calculator import calculate_differences_for_layer

class TestCalculator(unittest.TestCase):

    def setUp(self):
        self.ptn_file_path = "Data_ex/2025042401440800/02_0014046_001_002_001.ptn"
        self.dcm_file_path = "Data_ex/RP.1.2.840.113854.241506614174277151614979936366782948539.1.dcm"

        self.log_data = parse_ptn_file(self.ptn_file_path)
        plan_data = parse_dcm_file(self.dcm_file_path)
        self.plan_layer = next(iter(next(iter(plan_data['beams'].values()))['layers'].values()))


    def test_calculate_differences_smoke(self):
        """
        A simple smoke test to see if the function runs without crashing.
        """
        results = calculate_differences_for_layer(self.plan_layer, self.log_data)
        self.assertIsInstance(results, dict)

    def test_calculate_differences_keys(self):
        """
        Test that the results dictionary contains the expected keys.
        """
        results = calculate_differences_for_layer(self.plan_layer, self.log_data)
        self.assertIn('diff_x', results)
        self.assertIn('diff_y', results)
        self.assertIn('hist_fit_x', results)
        self.assertIn('hist_fit_y', results)

    def test_calculate_differences_data_shape(self):
        """
        Test that the difference arrays have the correct shape.
        """
        results = calculate_differences_for_layer(self.plan_layer, self.log_data)
        self.assertEqual(results['diff_x'].shape, self.log_data['x'].shape)
        self.assertEqual(results['diff_y'].shape, self.log_data['y'].shape)

    def test_hist_fit_results(self):
        """
        Test that the histogram fit results have the expected keys.
        """
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
