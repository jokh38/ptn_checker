import unittest
import os
import numpy as np
from unittest.mock import patch, MagicMock
import shutil

# Add src to path to allow for imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import the functions to be tested, including the private ones
from src.report_generator import (
    generate_report,
    _generate_error_bar_plot,
    _generate_position_plot
)

class TestReportGenerator(unittest.TestCase):

    def setUp(self):
        """Set up test data and output directory."""
        self.output_dir = "test_output"
        os.makedirs(self.output_dir, exist_ok=True)

        # Data for helper functions
        self.mean_diff = {'x': np.array([0.1, 0.2]), 'y': np.array([-0.1, -0.2])}
        self.std_diff = {'x': np.array([0.5, 0.6]), 'y': np.array([0.4, 0.5])}
        self.plan_positions = [
            np.array([[1, 2], [3, 4]]),  # Layer 1
            np.array([[5, 6], [7, 8]])   # Layer 2
        ]
        self.log_positions = [
            np.array([[1.1, 2.1], [3.1, 4.1], [1.1, 2.1], [3.1, 4.1], [1.1, 2.1], [3.1, 4.1], [1.1, 2.1], [3.1, 4.1], [1.1, 2.1], [3.1, 4.1], [1.1, 2.1]]), # Layer 1
            np.array([[5.1, 6.1], [7.1, 8.1]])   # Layer 2
        ]

        # Data for the main generate_report function
        self.plan_data = {
            'mean_diff': self.mean_diff,
            'std_diff': self.std_diff,
            'positions': self.plan_positions
        }
        self.log_data = {
            'positions': self.log_positions
        }

    def tearDown(self):
        """Remove the output directory after tests."""
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.subplots')
    def test_generate_error_bar_plot(self, mock_subplots, mock_savefig):
        """Test the _generate_error_bar_plot helper function directly."""
        mock_fig, (mock_ax1, mock_ax2) = MagicMock(), (MagicMock(), MagicMock())
        mock_subplots.return_value = (mock_fig, (mock_ax1, mock_ax2))

        _generate_error_bar_plot(self.mean_diff, self.std_diff, self.output_dir)

        # Assert that subplots was called correctly
        mock_subplots.assert_called_once_with(2, 1, figsize=(10, 8))

        # Assert for X-position plot
        layers = np.arange(1, len(self.mean_diff['x']) + 1)
        # Using np.array_equal for comparing numpy arrays in mock calls
        self.assertTrue(np.array_equal(mock_ax1.errorbar.call_args[0][0], layers))
        self.assertTrue(np.array_equal(mock_ax1.errorbar.call_args[0][1], self.mean_diff['x']))
        self.assertTrue(np.array_equal(mock_ax1.errorbar.call_args[1]['yerr'], self.std_diff['x']))

        # Assert for Y-position plot
        self.assertTrue(np.array_equal(mock_ax2.errorbar.call_args[0][0], layers))
        self.assertTrue(np.array_equal(mock_ax2.errorbar.call_args[0][1], self.mean_diff['y']))
        self.assertTrue(np.array_equal(mock_ax2.errorbar.call_args[1]['yerr'], self.std_diff['y']))

        # Assert savefig was called
        mock_savefig.assert_called_once_with(f"{self.output_dir}/error_bar_plot.png")

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.subplots')
    def test_generate_position_plot(self, mock_subplots, mock_savefig):
        """Test the _generate_position_plot helper function directly."""
        mock_fig, mock_ax = MagicMock(), MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)
        mock_ax.get_legend.return_value = None

        _generate_position_plot(self.plan_positions, self.log_positions, self.output_dir)

        # Assert subplots was called correctly
        mock_subplots.assert_called_once_with(figsize=(10, 10))

        # Assert plot/scatter calls
        self.assertEqual(mock_ax.plot.call_count, 2)
        self.assertEqual(mock_ax.scatter.call_count, 2)

        # Assert savefig was called
        mock_savefig.assert_called_once_with(f"{self.output_dir}/position_comparison_plot.png")

    @patch('src.report_generator._generate_position_plot')
    @patch('src.report_generator._generate_error_bar_plot')
    def test_generate_report_calls_helpers(self, mock_error_plot, mock_position_plot):
        """Test that the main report function calls its helper plot functions."""
        generate_report(self.plan_data, self.log_data, self.output_dir)

        mock_error_plot.assert_called_once_with(
            self.plan_data['mean_diff'],
            self.plan_data['std_diff'],
            self.output_dir
        )
        mock_position_plot.assert_called_once_with(
            self.plan_data['positions'],
            self.log_data['positions'],
            self.output_dir
        )

    def test_output_directory_creation(self):
        """Test that generate_report creates the output directory if it doesn't exist."""
        temp_output_dir = "temp_test_dir_for_creation"
        if os.path.exists(temp_output_dir):
            shutil.rmtree(temp_output_dir)

        with patch('src.report_generator._generate_error_bar_plot'), \
             patch('src.report_generator._generate_position_plot'):
            generate_report(self.plan_data, self.log_data, temp_output_dir)

        self.assertTrue(os.path.exists(temp_output_dir))
        shutil.rmtree(temp_output_dir)

if __name__ == '__main__':
    unittest.main()