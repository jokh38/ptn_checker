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
    _generate_summary_page,
    _draw_layer_heatmap,
    _draw_analysis_info_panel,
    _generate_per_layer_position_plot,
    _save_plots_to_pdf_grid,
    _layer_passes,
    _spot_pass_summary,
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

    def test_draw_layer_heatmap_renders_all_layers(self):
        fig = plt.figure(figsize=(6, 4))
        title_ax = fig.add_subplot(3, 1, 1)
        header_ax = fig.add_subplot(2, 1, 1)
        ax = fig.add_subplot(2, 1, 2)
        heatmap_values = np.array([
            [0.1, 0.2, 0.3, 0.4],
            [0.5, 0.6, 0.7, 0.8],
            [0.9, 1.0, 1.1, 1.2],
            [0.2, 0.3, 0.4, 0.5],
            [0.6, 0.7, 0.8, 0.9],
            [1.0, 1.1, 1.2, 1.3],
        ])
        layer_labels = ["1", "2", "3", "4"]
        metric_labels = ["Mean", "Std", "Max", "Mean", "Std", "Max"]
        flag_rows = {
            "Fail": [False, True, False, False],
            "Fallback": [False, False, True, False],
        }

        image, flag_image = _draw_layer_heatmap(
            fig,
            title_ax,
            header_ax,
            ax,
            heatmap_values,
            layer_labels,
            metric_labels,
            flag_rows=flag_rows,
        )

        self.assertEqual((4, 6), image.get_array().shape)
        self.assertEqual((4, 1), flag_image.get_array().shape)
        self.assertTrue(any(text.get_text() == "Layer Heatmap" for text in title_ax.texts))
        self.assertEqual("Metric", ax.get_xlabel())
        self.assertEqual("Layer", ax.get_ylabel())
        self.assertEqual(
            ["Mean", "Std", "Max", "Mean", "Std", "Max"],
            [text.get_text() for text in header_ax.texts if text.get_text() in metric_labels],
        )
        group_labels = [text.get_text() for text in header_ax.texts]
        self.assertIn("X", group_labels)
        self.assertIn("Y", group_labels)
        self.assertEqual(1, group_labels.count("X"))
        self.assertEqual(1, group_labels.count("Y"))
        plt.close(fig)

    def test_draw_layer_heatmap_uses_prioritized_abbreviated_flag_column(self):
        fig = plt.figure(figsize=(6, 4))
        title_ax = fig.add_subplot(3, 1, 1)
        header_ax = fig.add_subplot(2, 1, 1)
        ax = fig.add_subplot(2, 1, 2)
        heatmap_values = np.array([
            [0.1, 0.2, 0.3, 0.4],
            [0.5, 0.6, 0.7, 0.8],
        ])
        layer_labels = ["1", "2", "3", "4"]
        metric_labels = ["Mean", "Std"]
        flag_rows = {
            "Fallback": [False, True, False, False],
            "Settle": [False, False, True, False],
            "Overlap": [False, False, False, True],
            "Fail": [True, False, False, False],
        }

        _, flag_image = _draw_layer_heatmap(
            fig,
            title_ax,
            header_ax,
            ax,
            heatmap_values,
            layer_labels,
            metric_labels,
            flag_rows=flag_rows,
        )

        self.assertIsNotNone(flag_image)
        flag_ax = flag_image.axes
        rendered_chars = [text.get_text() for text in flag_ax.texts]
        self.assertEqual(["FAIL", "FB", "NS", "OV"], rendered_chars[:4])
        legend_text = "\n".join(rendered_chars[4:])
        self.assertIn("FAIL = layer fail", legend_text)
        self.assertIn("FB = fallback to raw", legend_text)
        self.assertIn("NS = never settled", legend_text)
        self.assertIn("OV = low overlap", legend_text)
        plt.close(fig)

    def test_generate_summary_page_uses_trend_and_heatmap_panels(self):
        beam_data = self.report_data["Beam 1"]

        fig = _generate_summary_page("Beam 1", beam_data)
        axes_by_title = {ax.get_title(): ax for ax in fig.axes if ax.get_title()}
        title_axes = [
            ax for ax in fig.axes if any(text.get_text() == "Layer Heatmap" for text in ax.texts)
        ]

        trend_title_axes = [
            ax for ax in fig.axes if any(text.get_text() == "Layer Trend" for text in ax.texts)
        ]
        self.assertEqual(1, len(trend_title_axes))
        self.assertEqual(1, len(title_axes))
        # The trend plot axes (with yticks) is the one with ylabel "Layer"
        trend_plot_axes = [ax for ax in fig.axes if ax.get_ylabel() == "Layer" and len(ax.images) == 0]
        self.assertEqual(1, len(trend_plot_axes))
        self.assertGreaterEqual(len(trend_plot_axes[0].get_yticks()), 2)
        self.assertEqual(
            1,
            len([ax for ax in fig.axes if len(ax.images) == 1 and ax.get_ylabel() == "Layer"]),
        )
        plt.close(fig)

    def test_generate_summary_page_uses_human_readable_heatmap_headers(self):
        beam_data = self.report_data["Beam 1"]

        fig = _generate_summary_page("Beam 1", beam_data)
        heatmap_ax = next(ax for ax in fig.axes if len(ax.images) == 1 and ax.get_ylabel() == "Layer")
        header_ax = next(
            ax for ax in fig.axes
            if ax is not heatmap_ax and any(text.get_text() == "X" for text in ax.texts)
        )

        self.assertEqual(
            ["Mean", "Std", "Max", "Mean", "Std", "Max"],
            [text.get_text() for text in header_ax.texts if text.get_text() in ["Mean", "Std", "Max"]],
        )
        group_labels = [text.get_text() for text in header_ax.texts]
        self.assertIn("X", group_labels)
        self.assertIn("Y", group_labels)
        plt.close(fig)

    def test_generate_summary_page_uses_dedicated_heatmap_header_band(self):
        beam_data = self.report_data["Beam 1"]

        fig = _generate_summary_page("Beam 1", beam_data)
        heatmap_ax = next(ax for ax in fig.axes if len(ax.images) == 1 and ax.get_ylabel() == "Layer")
        header_ax = next(
            ax for ax in fig.axes
            if ax is not heatmap_ax and any(text.get_text() == "X" for text in ax.texts)
        )

        self.assertFalse(any(text.get_text() == "X" for text in heatmap_ax.texts))
        self.assertFalse(any(text.get_text() == "Y" for text in heatmap_ax.texts))
        self.assertTrue(any(text.get_text() == "X" for text in header_ax.texts))
        self.assertTrue(any(text.get_text() == "Y" for text in header_ax.texts))
        self.assertGreater(header_ax.get_position().y0, heatmap_ax.get_position().y1)
        plt.close(fig)

    def test_generate_summary_page_places_flag_legend_outside_colorbar(self):
        beam_data = self.report_data["Beam 1"]
        for idx, layer in enumerate(beam_data["layers"]):
            results = layer["results"]
            results["filtered_stats_fallback_to_raw"] = idx == 1
            results["settling_status"] = "never_settled" if idx == 2 else "settled"
            results["time_overlap_fraction"] = 0.8 if idx == 3 else 1.0
            if idx == 4:
                results["max_abs_diff_x"] = 4.5

        fig = _generate_summary_page("Beam 1", beam_data)
        flag_ax = next(
            ax for ax in fig.axes
            if [tick.get_text() for tick in ax.get_xticklabels()] == ["Flag"]
        )
        legend_ax = next(
            ax for ax in fig.axes
            if any("FAIL = layer fail" in text.get_text() for text in ax.texts)
        )
        colorbar_ax = next(
            ax for ax in fig.axes if ax.get_xlabel() == "Error severity (mm)"
        )

        legend_text = "\n".join(text.get_text() for text in legend_ax.texts if "=" in text.get_text())
        self.assertIn("FAIL = layer fail", legend_text)
        self.assertIn("FB = fallback to raw", legend_text)
        self.assertIn("NS = never settled", legend_text)
        self.assertIn("OV = low overlap", legend_text)
        self.assertLess(legend_ax.get_position().y1, colorbar_ax.get_position().y0)
        plt.close(fig)

    def test_generate_summary_page_uses_middle_right_panel_row_order(self):
        beam_data = self.report_data["Beam 1"]
        beam_data["layers"][0]["results"]["filtered_stats_fallback_to_raw"] = True

        fig = _generate_summary_page("Beam 1", beam_data)
        heatmap_ax = next(ax for ax in fig.axes if len(ax.images) == 1 and ax.get_ylabel() == "Layer")
        title_ax = next(
            ax for ax in fig.axes
            if ax is not heatmap_ax and any(text.get_text() == "Layer Heatmap" for text in ax.texts)
        )
        colorbar_ax = next(ax for ax in fig.axes if ax.get_xlabel() == "Error severity (mm)")
        legend_ax = next(
            ax for ax in fig.axes
            if any("FAIL = layer fail" in text.get_text() for text in ax.texts)
        )

        self.assertGreater(title_ax.get_position().y0, heatmap_ax.get_position().y1)
        self.assertLess(colorbar_ax.get_position().y1, heatmap_ax.get_position().y0)
        self.assertLess(legend_ax.get_position().y1, colorbar_ax.get_position().y0)
        plt.close(fig)

    def test_summary_page_uses_horizontal_xy_errorbar_trend(self):
        beam_data = self.report_data["Beam 1"]

        fig = _generate_summary_page("Beam 1", beam_data)
        trend_ax = next(
            ax for ax in fig.axes if ax.get_ylabel() == "Layer" and len(ax.images) == 0
        )
        _, legend_labels = trend_ax.get_legend_handles_labels()

        self.assertEqual("Deviation (mm)", trend_ax.get_xlabel())
        self.assertEqual("Layer", trend_ax.get_ylabel())
        self.assertIn("X mean ± std", legend_labels)
        self.assertIn("Y mean ± std", legend_labels)
        plt.close(fig)

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

    def test_spot_pass_summary_counts_passed_spots(self):
        results = {
            "diff_x": np.array([0.1, 0.2, 0.2, 4.0]),
            "diff_y": np.array([0.1, -0.2, 0.2, 4.0]),
            "assigned_spot_index": np.array([0, 0, 1, 1]),
        }

        passed_spots, total_spots = _spot_pass_summary(results)

        self.assertEqual(1, passed_spots)
        self.assertEqual(2, total_spots)

    def test_spot_pass_summary_uses_filtered_series_when_requested(self):
        results = {
            "diff_x": np.array([0.1, 4.0]),
            "diff_y": np.array([0.1, 4.0]),
            "filtered_diff_x": np.array([0.1]),
            "filtered_diff_y": np.array([0.1]),
            "assigned_spot_index": np.array([0, 0]),
            "sample_is_included_filtered_stats": np.array([True, False]),
        }

        passed_spots, total_spots = _spot_pass_summary(results, report_mode="filtered")

        self.assertEqual(1, passed_spots)
        self.assertEqual(1, total_spots)

    def test_analysis_info_panel_shows_criteria_and_settling(self):
        fig = plt.figure(figsize=(4, 5))
        ax = fig.add_subplot(1, 1, 1)
        ax.axis("off")
        layers_data = self.report_data["Beam 1"]["layers"]
        config = {
            "SETTLING_THRESHOLD_MM": 0.5,
            "SETTLING_CONSECUTIVE_SAMPLES": 10,
            "SETTLING_WINDOW_SAMPLES": 50,
            "ZERO_DOSE_FILTER_ENABLED": False,
        }

        _draw_analysis_info_panel(ax, layers_data, "raw", analysis_config=config)

        self.assertEqual("Analysis Info", ax.get_title())
        table = ax.tables[0]
        cell_texts = [
            table[row_idx, col_idx].get_text().get_text()
            for row_idx in range(1, len(table._cells) // 2 + 1)
            for col_idx in range(2)
            if (row_idx, col_idx) in table._cells
        ]
        cell_str = " ".join(cell_texts)
        self.assertIn("1.0 mm", cell_str)
        self.assertIn("1.5 mm", cell_str)
        self.assertIn("3.0 mm", cell_str)
        self.assertIn("0.50 mm", cell_str)
        self.assertIn("10", cell_str)
        self.assertIn("Disabled", cell_str)
        plt.close(fig)

    def test_analysis_info_panel_shows_zero_dose_when_enabled(self):
        fig = plt.figure(figsize=(4, 5))
        ax = fig.add_subplot(1, 1, 1)
        ax.axis("off")
        layers_data = self.report_data["Beam 1"]["layers"]
        config = {
            "SETTLING_THRESHOLD_MM": 0.5,
            "SETTLING_CONSECUTIVE_SAMPLES": 3,
            "SETTLING_WINDOW_SAMPLES": 10,
            "ZERO_DOSE_FILTER_ENABLED": True,
            "ZERO_DOSE_MAX_MU": 0.001,
            "ZERO_DOSE_BOUNDARY_HOLDOFF_S": 0.0006,
            "ZERO_DOSE_REPORT_MODE": "filtered",
        }

        _draw_analysis_info_panel(ax, layers_data, "filtered", analysis_config=config)

        table = ax.tables[0]
        cell_texts = [
            table[row_idx, col_idx].get_text().get_text()
            for row_idx in range(1, len(table._cells) // 2 + 1)
            for col_idx in range(2)
            if (row_idx, col_idx) in table._cells
        ]
        cell_str = " ".join(cell_texts)
        self.assertIn("Enabled", cell_str)
        self.assertIn("0.0010", cell_str)
        self.assertIn("0.0006 s", cell_str)
        self.assertIn("filtered", cell_str)
        plt.close(fig)

    def test_analysis_info_panel_works_without_config(self):
        fig = plt.figure(figsize=(4, 5))
        ax = fig.add_subplot(1, 1, 1)
        ax.axis("off")
        layers_data = self.report_data["Beam 1"]["layers"]

        _draw_analysis_info_panel(ax, layers_data, "raw")

        self.assertEqual("Analysis Info", ax.get_title())
        table = ax.tables[0]
        cell_texts = [
            table[row_idx, col_idx].get_text().get_text()
            for row_idx in range(1, len(table._cells) // 2 + 1)
            for col_idx in range(2)
            if (row_idx, col_idx) in table._cells
        ]
        cell_str = " ".join(cell_texts)
        # Criteria section always present
        self.assertIn("1.0 mm", cell_str)
        # No settling section without config
        self.assertNotIn("0.50 mm", cell_str)
        plt.close(fig)

    def test_summary_page_passes_analysis_config_to_panel(self):
        beam_data = self.report_data["Beam 1"]
        config = {
            "SETTLING_THRESHOLD_MM": 0.75,
            "SETTLING_CONSECUTIVE_SAMPLES": 5,
            "SETTLING_WINDOW_SAMPLES": 20,
            "ZERO_DOSE_FILTER_ENABLED": False,
        }

        fig = _generate_summary_page("Beam 1", beam_data, analysis_config=config)

        # Find the analysis info panel by its title
        info_axes = [ax for ax in fig.axes if ax.get_title() == "Analysis Info"]
        self.assertEqual(1, len(info_axes))
        table = info_axes[0].tables[0]
        cell_texts = [
            table[row_idx, col_idx].get_text().get_text()
            for row_idx in range(1, len(table._cells) // 2 + 1)
            for col_idx in range(2)
            if (row_idx, col_idx) in table._cells
        ]
        cell_str = " ".join(cell_texts)
        self.assertIn("0.75 mm", cell_str)
        plt.close(fig)


if __name__ == '__main__':
    unittest.main()
