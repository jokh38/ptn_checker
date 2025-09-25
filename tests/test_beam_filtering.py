import unittest
import os
import numpy as np
import tempfile
import shutil
import sys

# Add src to path to allow for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.log_parser import parse_ptn_file


class TestBeamFiltering(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ptn_file_path = os.path.join(self.test_dir, "test_beam_filtering.ptn")

        # Create test data with mixed Beam On (1) and Beam Off (0) states
        # Data format: x_raw, y_raw, x_size_raw, y_size_raw, dose1, dose2, layer, beam_on_off
        self.raw_data = np.array([
            1000, 2000, 300, 400, 50, 60, 1, 1,  # Beam On
            1010, 2020, 310, 410, 55, 65, 1, 0,  # Beam Off
            1020, 2040, 320, 420, 60, 70, 1, 1,  # Beam On
            1030, 2060, 330, 430, 65, 75, 1, 0,  # Beam Off
            1040, 2080, 340, 440, 70, 80, 1, 1   # Beam On
        ], dtype='>u2')
        self.raw_data.tofile(self.ptn_file_path)

        # Configuration parameters
        self.config = {
            'TIMEGAIN': 10.0,
            'XPOSOFFSET': 500.0,
            'YPOSOFFSET': 1500.0,
            'XPOSGAIN': 0.1,
            'YPOSGAIN': 0.2
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_beam_on_filtering(self):
        """Test that only Beam On data (beam_on_off == 1) is included in the results."""
        data = parse_ptn_file(self.ptn_file_path, self.config)

        # Should only have 3 data points (indices 0, 2, 4 from original data)
        expected_count = 3
        self.assertEqual(len(data['time_ms']), expected_count)
        self.assertEqual(len(data['x_raw']), expected_count)
        self.assertEqual(len(data['beam_on_off']), expected_count)

        # All beam_on_off values should be 1
        np.testing.assert_array_equal(data['beam_on_off'], np.array([1, 1, 1]))

        # Check that the correct x_raw values are included (original indices 0, 2, 4)
        expected_x_raw = np.array([1000, 1020, 1040], dtype=np.float32)
        np.testing.assert_array_equal(data['x_raw'], expected_x_raw)

        # Check that the correct y_raw values are included
        expected_y_raw = np.array([2000, 2040, 2080], dtype=np.float32)
        np.testing.assert_array_equal(data['y_raw'], expected_y_raw)

    def test_filtered_dose_calculation(self):
        """Test that cumulative MU is recalculated correctly for filtered data."""
        data = parse_ptn_file(self.ptn_file_path, self.config)

        # Expected dose1 values for Beam On records: 50, 60, 70
        expected_dose1 = np.array([50, 60, 70], dtype=np.float32)
        np.testing.assert_array_equal(data['dose1_au'], expected_dose1)

        # Expected dose2 values for Beam On records: 60, 70, 80
        expected_dose2 = np.array([60, 70, 80], dtype=np.float32)
        np.testing.assert_array_equal(data['dose2_au'], expected_dose2)

        # Expected cumulative MU: cumsum([110, 130, 150]) = [110, 240, 390]
        expected_cumulative_mu = np.array([110, 240, 390], dtype=np.float32)
        np.testing.assert_array_equal(data['mu'], expected_cumulative_mu)

    def test_filtered_position_calculation(self):
        """Test that calibrated positions are calculated correctly for filtered data."""
        data = parse_ptn_file(self.ptn_file_path, self.config)

        # Expected x_mm values: (x_raw - 500) * 0.1 for Beam On records
        # x_raw values: [1000, 1020, 1040]
        expected_x_mm = np.array([(1000-500)*0.1, (1020-500)*0.1, (1040-500)*0.1])
        np.testing.assert_allclose(data['x_mm'], expected_x_mm, rtol=1e-6)

        # Expected y_mm values: (y_raw - 1500) * 0.2 for Beam On records
        # y_raw values: [2000, 2040, 2080]
        expected_y_mm = np.array([(2000-1500)*0.2, (2040-1500)*0.2, (2080-1500)*0.2])
        np.testing.assert_allclose(data['y_mm'], expected_y_mm, rtol=1e-6)

    def test_all_beam_off_data(self):
        """Test behavior when all data has beam_on_off == 0."""
        # Create test file with all Beam Off data
        beam_off_file = os.path.join(self.test_dir, "all_beam_off.ptn")
        all_beam_off_data = np.array([
            1000, 2000, 300, 400, 50, 60, 1, 0,  # Beam Off
            1010, 2020, 310, 410, 55, 65, 1, 0,  # Beam Off
        ], dtype='>u2')
        all_beam_off_data.tofile(beam_off_file)

        data = parse_ptn_file(beam_off_file, self.config)

        # Should result in empty arrays
        self.assertEqual(len(data['time_ms']), 0)
        self.assertEqual(len(data['x_raw']), 0)
        self.assertEqual(len(data['mu']), 0)


if __name__ == '__main__':
    unittest.main()