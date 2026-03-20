import unittest
import os
import numpy as np
from unittest.mock import patch, MagicMock, call
import shutil
import tempfile
import matplotlib.pyplot as plt

from src.report_generator import (
    generate_report,
    _generate_error_bar_plot_for_beam,
    _generate_per_layer_position_plot,
    _save_plots_to_pdf_grid,
    _layer_passes,
)


class TestReportGenerator(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "test_output")
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
                    },
                    {
                        "layer_index": 2,
                        "results": {
                            "mean_diff_x": 0.3, "mean_diff_y": -0.3,
                            "std_diff_x": 0.7, "std_diff_y": 0.6,
                            "plan_positions": np.array([[9, 10], [11, 12]]),
                            "log_positions": np.array([[9.1, 10.1], [11.1, 12.1]])
                        }
                    },
                    {
                        "layer_index": 3,
                        "results": {
                            "mean_diff_x": 0.4, "mean_diff_y": -0.4,
                            "std_diff_x": 0.8, "std_diff_y": 0.7,
                            "plan_positions": np.array([[13, 14], [15, 16]]),
                            "log_positions": np.array([[13.1, 14.1], [15.1, 16.1]])
                        }
                    },
                    {
                        "layer_index": 4,
                        "results": {
                            "mean_diff_x": 0.5, "mean_diff_y": -0.5,
                            "std_diff_x": 0.9, "std_diff_y": 0.8,
                            "plan_positions": np.array([[17, 18], [19, 20]]),
                            "log_positions": np.array([[17.1, 18.1], [19.1, 20.1]])
                        }
                    },
                    {
                        "layer_index": 5,
                        "results": {
                            "mean_diff_x": 0.6, "mean_diff_y": -0.6,
                            "std_diff_x": 1.0, "std_diff_y": 0.9,
                            "plan_positions": np.array([[21, 22], [23, 24]]),
                            "log_positions": np.array([[21.1, 22.1], [23.1, 24.1]])
                        }
                    },
                    {
                        "layer_index": 6,
                        "results": {
                            "mean_diff_x": 0.7, "mean_diff_y": -0.7,
                            "std_diff_x": 1.1, "std_diff_y": 1.0,
                            "plan_positions": np.array([[25, 26], [27, 28]]),
                            "log_positions": np.array([[25.1, 26.1], [27.1, 28.1]])
                        }
                    }
                ]
            }
        }

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_generate_error_bar_plot_for_beam(self):
        beam_name = "Beam 1"
        beam = self.report_data.get(beam_name, {})
        layers_data = beam.get('layers', [])
        fig = _generate_error_bar_plot_for_beam(beam_name, layers_data)
        self.assertIsInstance(fig, plt.Figure)
        plt.close(fig)

    def test_generate_per_layer_position_plot(self):
        beam = self.report_data.get("Beam 1", {})
        layer_data = beam.get('layers', [{}])[0]
        results = layer_data.get('results', {})
        # Mock global coordinates for testing
        global_min_coords = np.array([0, 0])
        global_max_coords = np.array([10, 10])
        fig = _generate_per_layer_position_plot(
            results.get('plan_positions', np.empty((0, 2))),
            results.get('log_positions', np.empty((0, 2))),
            layer_data.get('layer_index', 0),
            "Beam 1",
            global_min_coords,
            global_max_coords
        )
        self.assertIsInstance(fig, plt.Figure)
        plt.close(fig)

    def test_save_plots_to_pdf_grid(self):
        plots = [plt.figure(), plt.figure(), plt.figure(), plt.figure(), plt.figure(), plt.figure()]
        for fig in plots:
            fig.add_subplot(1, 1, 1)  # Add axes to the figure

        with patch('matplotlib.backends.backend_pdf.PdfPages') as mock_pdf_pages:
            mock_pdf = mock_pdf_pages.return_value
            _save_plots_to_pdf_grid(mock_pdf, plots, "Beam 1")
            mock_pdf.savefig.assert_called_once()
        plt.close('all')

    def test_generate_report_creates_pdf(self):
        expected_pdf_path = os.path.join(self.output_dir, "analysis_report.pdf")
        if os.path.exists(expected_pdf_path):
            os.remove(expected_pdf_path)

        generate_report(self.report_data, self.output_dir)
        self.assertTrue(os.path.exists(expected_pdf_path))

    def test_generate_report_handles_out_of_range_summary_histogram(self):
        report_data = {
            "Beam 1": {
                "layers": [
                    {
                        "layer_index": 0,
                        "results": {
                            "mean_diff_x": 0.1,
                            "mean_diff_y": 25.0,
                            "std_diff_x": 0.5,
                            "std_diff_y": 1.0,
                            "rmse_x": 0.5,
                            "rmse_y": 25.0,
                            "max_abs_diff_x": 1.0,
                            "max_abs_diff_y": 25.0,
                            "p95_abs_diff_x": 1.0,
                            "p95_abs_diff_y": 25.0,
                            "diff_x": np.array([0.0, 0.2, -0.2]),
                            "diff_y": np.array([20.0, 25.0, 30.0]),
                            "plan_positions": np.array([[0.0, 0.0], [1.0, 1.0]]),
                            "log_positions": np.array([[0.1, 20.0], [1.1, 30.0]]),
                        },
                    }
                ]
            }
        }

        expected_pdf_path = os.path.join(self.output_dir, "analysis_report.pdf")
        generate_report(report_data, self.output_dir)
        self.assertTrue(os.path.exists(expected_pdf_path))

    def test_layer_passes_uses_filtered_metrics_when_requested(self):
        results = {
            "mean_diff_x": 0.1,
            "mean_diff_y": 0.1,
            "std_diff_x": 0.5,
            "std_diff_y": 0.5,
            "max_abs_diff_x": 8.0,
            "max_abs_diff_y": 8.0,
            "filtered_mean_diff_x": 0.1,
            "filtered_mean_diff_y": 0.1,
            "filtered_std_diff_x": 0.5,
            "filtered_std_diff_y": 0.5,
            "filtered_max_abs_diff_x": 1.0,
            "filtered_max_abs_diff_y": 1.0,
        }

        self.assertFalse(_layer_passes(results))
        self.assertTrue(_layer_passes(results, report_mode="filtered"))

if __name__ == '__main__':
    unittest.main()
