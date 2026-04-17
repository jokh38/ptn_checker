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
    _generate_point_gamma_summary_page,
    _generate_per_layer_position_plot,
    _save_plots_to_pdf_grid,
    _layer_passes,
    _spot_pass_summary,
)
from src.report_layout import (
    _draw_layer_heatmap,
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
        self.point_gamma_report_data = {
            "Beam 1": {
                "beam_number": 1,
                "layers": [
                    {
                        "layer_index": 0,
                        "results": {
                            "pass_rate": 0.96,
                            "gamma_mean": 0.31,
                            "gamma_max": 0.88,
                            "evaluated_point_count": 12,
                            "position_error_mean_mm": 0.22,
                            "count_error_mean": 0.015,
                            "mean_diff_x": 0.1,
                            "mean_diff_y": -0.1,
                            "std_diff_x": 0.2,
                            "std_diff_y": 0.3,
                            "rmse_x": 0.22,
                            "rmse_y": 0.32,
                            "max_abs_diff_x": 0.5,
                            "max_abs_diff_y": 0.6,
                            "p95_abs_diff_x": 0.4,
                            "p95_abs_diff_y": 0.5,
                            "diff_x": np.array([0.0, 0.1, 0.2]),
                            "diff_y": np.array([0.0, -0.1, -0.2]),
                            "plan_positions": np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]]),
                            "log_positions": np.array([[0.0, 0.0], [1.1, 0.9], [2.2, 1.8]]),
                            "gamma_map": np.array([[0.2, 0.4], [0.1, 0.3]]),
                        },
                    }
                ],
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

    def test_generate_point_gamma_summary_page_includes_gamma_metadata_and_pass_ratio(self):
        beam_data = self.point_gamma_report_data["Beam 1"]

        fig = _generate_point_gamma_summary_page(
            "Beam 1",
            beam_data,
            patient_id="12345",
            patient_name="Test^Point",
            analysis_config={
                "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
                "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
                "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            },
        )

        rendered_parts = []
        rendered_parts.extend(text.get_text() for text in fig.texts)
        for ax in fig.axes:
            rendered_parts.extend(text.get_text() for text in ax.texts)
            for table in ax.tables:
                rendered_parts.extend(
                    cell.get_text().get_text()
                    for cell in table.get_celld().values()
                )
        rendered_text = " ".join(rendered_parts)
        self.assertIn("Gamma pass (%)", rendered_text)
        self.assertIn("Distance to agreement", rendered_text)
        self.assertIn("Lower fluence cutoff", rendered_text)
        self.assertIn("Count threshold", rendered_text)
        self.assertIn("Point Gamma", rendered_text)
        summary_title = next(text for text in fig.texts if text.get_text() == "Point Gamma Summary")
        self.assertEqual("bold", summary_title.get_fontweight())
        plt.close(fig)

    def test_generate_point_gamma_summary_page_uses_stacked_top_summary_tables(self):
        beam_data = self.point_gamma_report_data["Beam 1"]

        fig = _generate_point_gamma_summary_page(
            "Beam 1",
            beam_data,
            patient_id="12345",
            patient_name="Test^Point",
            analysis_config={
                "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
                "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
                "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            },
        )

        table_titles = [
            ax.get_title()
            for ax in fig.axes
            if ax.get_title() in {"Position Summary", "Gamma Summary", "Point Gamma Summary"}
        ]
        combined_text = " ".join(
            cell.get_text().get_text()
            for ax in fig.axes
            for table in ax.tables
            for cell in table.get_celld().values()
        )

        self.assertNotIn("Position Summary", table_titles)
        self.assertIn("Gamma Summary", table_titles)
        self.assertNotIn("Point Gamma Summary", table_titles)
        self.assertNotIn("Radial", combined_text)
        self.assertIn("Gamma pass (%)", combined_text)
        self.assertIn("Evaluated points", combined_text)
        plt.close(fig)

    def test_generate_point_gamma_summary_page_does_not_duplicate_bottom_summary_labels(self):
        beam_data = self.point_gamma_report_data["Beam 1"]

        fig = _generate_point_gamma_summary_page(
            "Beam 1",
            beam_data,
            patient_id="12345",
            patient_name="Test^Point",
            analysis_config={
                "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
                "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
                "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            },
        )

        analysis_ax = next(ax for ax in fig.axes if ax.get_title() == "Config / Info")
        rendered_texts = [text.get_text() for text in analysis_ax.texts]
        self.assertNotIn("Distance to agreement: 2.0 mm", rendered_texts)
        self.assertNotIn("Count threshold: 5.0% of peak plan count", rendered_texts)
        self.assertNotIn("Lower fluence cutoff: 10.0% of peak plan count", rendered_texts)
        plt.close(fig)

    def test_generate_point_gamma_summary_page_uses_horizontal_gamma_and_config_tables(self):
        beam_data = self.point_gamma_report_data["Beam 1"]

        fig = _generate_point_gamma_summary_page(
            "Beam 1",
            beam_data,
            patient_id="12345",
            patient_name="Test^Point",
            analysis_config={
                "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
                "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
                "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            },
        )

        gamma_ax = next(ax for ax in fig.axes if ax.get_title() == "Gamma Summary")
        config_ax = next(ax for ax in fig.axes if ax.get_title() == "Config / Info")
        gamma_table = next(iter(gamma_ax.tables))
        config_table = next(iter(config_ax.tables))

        gamma_rows = max(row for row, _ in gamma_table.get_celld().keys()) + 1
        config_rows = max(row for row, _ in config_table.get_celld().keys()) + 1
        gamma_text = " ".join(
            cell.get_text().get_text()
            for cell in gamma_table.get_celld().values()
        )
        config_text = " ".join(
            cell.get_text().get_text()
            for cell in config_table.get_celld().values()
        )

        self.assertEqual(2, gamma_rows)
        self.assertEqual(2, config_rows)
        self.assertIn("Gamma mean", gamma_text)
        self.assertIn("Gamma max", gamma_text)
        self.assertIn("Evaluated points", gamma_text)
        self.assertIn("Distance to agreement", config_text)
        self.assertIn("Count threshold", config_text)
        self.assertIn("Lower fluence cutoff", config_text)
        plt.close(fig)

    def test_generate_point_gamma_summary_page_removes_bottom_right_panel(self):
        beam_data = self.point_gamma_report_data["Beam 1"]

        fig = _generate_point_gamma_summary_page(
            "Beam 1",
            beam_data,
            patient_id="12345",
            patient_name="Test^Point",
            analysis_config={
                "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
                "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
                "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            },
        )

        rendered_text = " ".join(
            text.get_text()
            for ax in fig.axes
            for text in ax.texts
        )
        self.assertNotIn("Lowest Gamma Pass", rendered_text)
        plt.close(fig)

    def test_generate_point_gamma_summary_page_uses_gamma_pass_in_right_side_heatmap_column(self):
        beam_data = self.point_gamma_report_data["Beam 1"]

        fig = _generate_point_gamma_summary_page(
            "Beam 1",
            beam_data,
            patient_id="12345",
            patient_name="Test^Point",
            analysis_config={
                "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
                "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
                "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            },
        )

        heatmap_ax = next(ax for ax in fig.axes if len(ax.images) == 1 and ax.get_ylabel() == "Layer")
        group_header_ax = next(
            ax
            for ax in fig.axes
            if ax is not heatmap_ax
            and abs(ax.get_position().x0 - heatmap_ax.get_position().x0) < 0.02
            and ax.get_position().y0 >= heatmap_ax.get_position().y1 - 0.001
            and any(
                cell.get_text().get_text() == "X"
                for table in ax.tables
                for cell in table.get_celld().values()
            )
        )
        side_header_ax = next(
            ax
            for ax in fig.axes
            if ax is not heatmap_ax
            and ax.get_position().x0 > heatmap_ax.get_position().x1
            and ax.get_position().y0 >= heatmap_ax.get_position().y1 - 0.001
            and any(
                cell.get_text().get_text() == "Gamma"
                for table in ax.tables
                for cell in table.get_celld().values()
            )
        )
        header_texts = [
            cell.get_text().get_text()
            for ax in (group_header_ax, side_header_ax)
            for table in ax.tables
            for cell in table.get_celld().values()
        ]
        side_ax = next(
            ax
            for ax in fig.axes
            if ax is not heatmap_ax and len(ax.images) == 1 and ax.get_ylabel() == ""
        )

        self.assertEqual((1, 6), np.asarray(heatmap_ax.images[0].get_array(), dtype=float).shape)
        self.assertEqual((1, 1), np.asarray(side_ax.images[0].get_array(), dtype=float).shape)
        self.assertIn("Gamma", header_texts)
        self.assertNotIn("Flag", header_texts)
        self.assertFalse(any(ax.get_title() == "Gamma Pass Ratio" for ax in fig.axes))
        plt.close(fig)

    def test_generate_report_writes_point_gamma_summary_and_detail_pdfs_when_detail_enabled(self):
        summary_pdf = os.path.join(
            self.output_dir,
            "PTN_report_case123_Beam 1_2026-04-17.pdf",
        )
        detail_pdf = os.path.join(
            self.output_dir,
            "PTN_report_case123_Beam 1_2026-04-17_detail.pdf",
        )

        generate_report(
            self.point_gamma_report_data,
            self.output_dir,
            report_name="PTN_report_case123_2026-04-17",
            analysis_mode="point_gamma",
            report_detail_pdf=True,
            analysis_config={
                "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
                "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
                "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            },
        )

        self.assertTrue(os.path.exists(summary_pdf))
        self.assertTrue(os.path.exists(detail_pdf))

    def test_generate_report_skips_point_gamma_detail_pdf_when_disabled(self):
        summary_pdf = os.path.join(
            self.output_dir,
            "PTN_report_case124_Beam 1_2026-04-17.pdf",
        )
        detail_pdf = os.path.join(
            self.output_dir,
            "PTN_report_case124_Beam 1_2026-04-17_detail.pdf",
        )

        generate_report(
            self.point_gamma_report_data,
            self.output_dir,
            report_name="PTN_report_case124_2026-04-17",
            analysis_mode="point_gamma",
            report_detail_pdf=False,
            analysis_config={
                "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
                "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
                "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            },
        )

        self.assertTrue(os.path.exists(summary_pdf))
        self.assertFalse(os.path.exists(detail_pdf))

    def test_draw_layer_heatmap_renders_all_layers(self):
        fig = plt.figure(figsize=(6, 4))
        title_ax = fig.add_subplot(3, 1, 1)
        group_header_ax = fig.add_subplot(4, 1, 1)
        metric_header_ax = fig.add_subplot(4, 1, 2)
        side_header_ax = fig.add_subplot(4, 2, 2)
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
        image, flag_image = _draw_layer_heatmap(
            fig,
            title_ax,
            group_header_ax,
            metric_header_ax,
            side_header_ax,
            ax,
            heatmap_values,
            layer_labels,
            metric_labels,
        )

        self.assertEqual((4, 6), image.get_array().shape)
        self.assertIsNone(flag_image)
        self.assertTrue(any(text.get_text() == "Layer Heatmap" for text in title_ax.texts))
        self.assertEqual("Metric", ax.get_xlabel())
        self.assertEqual("Layer", ax.get_ylabel())
        self.assertEqual(
            ["Mean", "Std", "Max", "Mean", "Std", "Max"],
            [
                cell.get_text().get_text()
                for table in metric_header_ax.tables
                for cell in table.get_celld().values()
                if cell.get_text().get_text() in metric_labels
            ],
        )
        group_labels = [
            cell.get_text().get_text()
            for table in group_header_ax.tables
            for cell in table.get_celld().values()
        ]
        self.assertIn("X", group_labels)
        self.assertIn("Y", group_labels)
        self.assertEqual(1, group_labels.count("X"))
        self.assertEqual(1, group_labels.count("Y"))
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


if __name__ == '__main__':
    unittest.main()
