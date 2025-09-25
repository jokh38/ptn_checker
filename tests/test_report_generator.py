import unittest
import os
import numpy as np
from unittest.mock import patch, MagicMock
import shutil
import matplotlib.pyplot as plt

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

    def test_generate_error_bar_plot_returns_figure(self):
        """Test the _generate_error_bar_plot helper returns a Figure object."""
        # No mocks needed, we are testing the function's output directly
        fig = _generate_error_bar_plot(self.mean_diff, self.std_diff)
        self.assertIsInstance(fig, plt.Figure)
        plt.close(fig) # Prevent figure from displaying in test runners

    def test_generate_position_plot_returns_figure(self):
        """Test the _generate_position_plot helper returns a Figure object."""
        fig = _generate_position_plot(self.plan_positions, self.log_positions)
        self.assertIsInstance(fig, plt.Figure)
        plt.close(fig) # Prevent figure from displaying

    @patch('src.report_generator._generate_position_plot')
    @patch('src.report_generator._generate_error_bar_plot')
    def test_generate_report_calls_helpers(self, mock_error_plot, mock_position_plot):
        """Test that the main report function calls its helper plot functions."""
        # Make the mocked helpers return a dummy figure, because the main function
        # will try to call pdf.savefig() on their return value.
        mock_figure = plt.figure()
        mock_error_plot.return_value = mock_figure
        mock_position_plot.return_value = mock_figure

        generate_report(self.plan_data, self.log_data, self.output_dir)

        mock_error_plot.assert_called_once_with(
            self.plan_data['mean_diff'],
            self.plan_data['std_diff']
        )
        mock_position_plot.assert_called_once_with(
            self.plan_data['positions'],
            self.log_data['positions']
        )
        plt.close(mock_figure)

    def test_output_directory_creation(self):
        """Test that generate_report creates the output directory if it doesn't exist."""
        temp_output_dir = "temp_test_dir_for_creation"
        if os.path.exists(temp_output_dir):
            shutil.rmtree(temp_output_dir)

        # We still need to mock the helpers, and they need to return a figure
        with patch('src.report_generator._generate_error_bar_plot') as mock_err, \
             patch('src.report_generator._generate_position_plot') as mock_pos:
            mock_figure = plt.figure()
            mock_err.return_value = mock_figure
            mock_pos.return_value = mock_figure
            generate_report(self.plan_data, self.log_data, temp_output_dir)
            plt.close(mock_figure)

        self.assertTrue(os.path.exists(temp_output_dir))
        shutil.rmtree(temp_output_dir)

    def test_generate_report_creates_pdf(self):
        """
        Test that `generate_report` creates a PDF file in the output directory.
        """
        expected_pdf_path = os.path.join(self.output_dir, "analysis_report.pdf")
        if os.path.exists(expected_pdf_path):
            os.remove(expected_pdf_path)

        # This is a real run, so no mocks needed
        generate_report(self.plan_data, self.log_data, self.output_dir)
        self.assertTrue(os.path.exists(expected_pdf_path), "PDF file was not created.")

    @patch('src.report_generator.PdfPages', autospec=True)
    @patch('src.report_generator._generate_position_plot')
    @patch('src.report_generator._generate_error_bar_plot')
    def test_generate_report_uses_pdfpages(self, mock_err_plot, mock_pos_plot, mock_pdf_pages):
        """
        Test that `generate_report` uses the PdfPages backend to save figures.
        """
        # Mock the helper functions to return a real figure object
        mock_figure = plt.figure()
        mock_err_plot.return_value = mock_figure
        mock_pos_plot.return_value = mock_figure

        # Mock the PdfPages object itself to check its methods
        mock_pdf_instance = mock_pdf_pages.return_value.__enter__.return_value

        generate_report(self.plan_data, self.log_data, self.output_dir)

        # Check that PdfPages was instantiated with the correct path
        mock_pdf_pages.assert_called_once_with(os.path.join(self.output_dir, "analysis_report.pdf"))

        # Check that savefig was called on the pdf object for each generated plot
        # 1 for error bar + 1 for combined position + 2 for the two layers
        expected_call_count = 1 + 1 + len(self.plan_positions)
        self.assertEqual(mock_pdf_instance.savefig.call_count, expected_call_count)
        mock_pdf_instance.savefig.assert_any_call(mock_figure)

        plt.close(mock_figure)


if __name__ == '__main__':
    unittest.main()