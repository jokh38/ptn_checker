import unittest
import os
import numpy as np
from unittest.mock import patch, MagicMock, call
import shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.report_generator import (
    generate_report,
    _generate_error_bar_plot_for_beam,
    _generate_per_layer_position_plot,
    _save_plots_to_pdf_grid
)

class TestReportGenerator(unittest.TestCase):

    def setUp(self):
        self.output_dir = "test_output"
        os.makedirs(self.output_dir, exist_ok=True)

        self.report_data = {
            "Beam 1": {
                "layers": [
                    {
                        "layer_index": 0,
                        "results": {
                            "mean_diff_x": 0.1, "mean_diff_y": -0.1,
                            "std_diff_x": 0.5, "std_diff_y": 0.4,
                            "plan_positions": np.array([[1, 2], [3, 4]]),
                            "log_positions": np.array([[1.1, 2.1], [3.1, 4.1]])
                        }
                    },
                    {
                        "layer_index": 1,
                        "results": {
                            "mean_diff_x": 0.2, "mean_diff_y": -0.2,
                            "std_diff_x": 0.6, "std_diff_y": 0.5,
                            "plan_positions": np.array([[5, 6], [7, 8]]),
                            "log_positions": np.array([[5.1, 6.1], [7.1, 8.1]])
                        }
                    }
                ]
            }
        }

    def tearDown(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_generate_error_bar_plot_for_beam(self):
        beam_name = "Beam 1"
        layers_data = self.report_data[beam_name]['layers']
        fig = _generate_error_bar_plot_for_beam(beam_name, layers_data)
        self.assertIsInstance(fig, plt.Figure)
        plt.close(fig)

    def test_generate_per_layer_position_plot(self):
        layer_data = self.report_data["Beam 1"]['layers'][0]
        fig = _generate_per_layer_position_plot(
            layer_data['results']['plan_positions'],
            layer_data['results']['log_positions'],
            layer_data['layer_index'],
            "Beam 1"
        )
        self.assertIsInstance(fig, plt.Figure)
        plt.close(fig)

    def test_save_plots_to_pdf_grid(self):
        plots = [plt.figure(), plt.figure()]
        for fig in plots:
            fig.add_subplot(1, 1, 1)  # Add axes to the figure

        with patch('matplotlib.backends.backend_pdf.PdfPages') as mock_pdf_pages:
            mock_pdf = mock_pdf_pages.return_value
            _save_plots_to_pdf_grid(mock_pdf, plots, "Beam 1")
            mock_pdf.savefig.assert_called_once()
        plt.close('all')

    @patch('src.report_generator._generate_error_bar_plot_for_beam')
    @patch('src.report_generator._generate_per_layer_position_plot')
    @patch('src.report_generator._save_plots_to_pdf_grid')
    def test_generate_report_calls_helpers(self, mock_save_grid, mock_per_layer_plot, mock_error_bar_plot):
        mock_fig = plt.figure()
        mock_error_bar_plot.return_value = mock_fig
        mock_per_layer_plot.return_value = mock_fig

        generate_report(self.report_data, self.output_dir)

        mock_error_bar_plot.assert_called_once_with("Beam 1", self.report_data["Beam 1"]['layers'])

        self.assertEqual(mock_per_layer_plot.call_count, 2)
        mock_save_grid.assert_called_once()

        plt.close(mock_fig)

    def test_generate_report_creates_pdf(self):
        expected_pdf_path = os.path.join(self.output_dir, "analysis_report.pdf")
        if os.path.exists(expected_pdf_path):
            os.remove(expected_pdf_path)

        generate_report(self.report_data, self.output_dir)
        self.assertTrue(os.path.exists(expected_pdf_path))

if __name__ == '__main__':
    unittest.main()