import unittest
import os
import numpy as np

# Add src to path to allow for imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.report_generator import generate_report

class TestReportGenerator(unittest.TestCase):

    def setUp(self):
        self.output_path = "test_report.pdf"
        self.plan_data = {
            'patient_name': 'Test Patient',
            'patient_id': '12345'
        }
        self.analysis_results = {
            "Beam 1": {
                1: {
                    'diff_x': np.random.normal(0, 0.5, 1000),
                    'diff_y': np.random.normal(0, 0.5, 1000),
                    'hist_fit_x': {'amplitude': 1, 'mean': 0.1, 'stddev': 0.5},
                    'hist_fit_y': {'amplitude': 1, 'mean': -0.1, 'stddev': 0.45}
                },
                2: {
                    'diff_x': np.random.normal(0, 0.5, 1000),
                    'diff_y': np.random.normal(0, 0.5, 1000),
                    'hist_fit_x': {'amplitude': 1, 'mean': 0.2, 'stddev': 0.6},
                    'hist_fit_y': {'amplitude': 1, 'mean': -0.2, 'stddev': 0.55}
                }
            }
        }

    def tearDown(self):
        if os.path.exists(self.output_path):
            os.remove(self.output_path)

    def test_generate_report_smoke(self):
        """
        Test that the report generation function runs and creates a file.
        """
        generate_report(self.plan_data, self.analysis_results, self.output_path)
        self.assertTrue(os.path.exists(self.output_path))

    def test_generate_report_file_size(self):
        """
        Test that the generated report file is not empty.
        """
        generate_report(self.plan_data, self.analysis_results, self.output_path)
        self.assertGreater(os.path.getsize(self.output_path), 0)

if __name__ == '__main__':
    unittest.main()
