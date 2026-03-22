import csv
import os
import tempfile
import unittest

import numpy as np

from src.report_csv_exporter import export_report_csv


class TestReportCsvExporter(unittest.TestCase):
    def test_export_report_csv_writes_filtered_metrics_and_fallback_flags(self):
        report_data = {
            "_patient_id": "123456",
            "_patient_name": "Test^Patient",
            "Beam / 1": {
                "beam_number": 7,
                "layers": [
                    {
                        "layer_index": 0,
                        "results": {
                            "diff_x": np.array([5.0, 5.0]),
                            "diff_y": np.array([5.0, 5.0]),
                            "filtered_diff_x": np.array([0.1, 0.2]),
                            "filtered_diff_y": np.array([0.1, 0.2]),
                            "assigned_spot_index": np.array([0, 0]),
                            "sample_is_included_filtered_stats": np.array([True, True]),
                            "mean_diff_x": 5.0,
                            "mean_diff_y": 5.0,
                            "std_diff_x": 5.0,
                            "std_diff_y": 5.0,
                            "rmse_x": 5.0,
                            "rmse_y": 5.0,
                            "max_abs_diff_x": 5.0,
                            "max_abs_diff_y": 5.0,
                            "p95_abs_diff_x": 5.0,
                            "p95_abs_diff_y": 5.0,
                            "filtered_mean_diff_x": 0.1,
                            "filtered_mean_diff_y": 0.2,
                            "filtered_std_diff_x": 0.3,
                            "filtered_std_diff_y": 0.4,
                            "filtered_rmse_x": 0.5,
                            "filtered_rmse_y": 0.6,
                            "filtered_max_abs_diff_x": 0.7,
                            "filtered_max_abs_diff_y": 0.8,
                            "filtered_p95_abs_diff_x": 0.9,
                            "filtered_p95_abs_diff_y": 1.0,
                            "filtered_stats_fallback_to_raw": False,
                            "num_included_samples": 2,
                            "num_filtered_samples": 0,
                            "filtered_sample_fraction": 0.0,
                            "filtered_mu_fraction_estimate": 0.0,
                            "time_overlap_fraction": 1.0,
                            "settling_samples_count": 0,
                            "settling_status": "settled",
                        },
                    }
                ],
            },
        }

        with tempfile.TemporaryDirectory() as output_dir:
            written_files = export_report_csv(
                report_data,
                output_dir,
                report_mode="filtered",
            )

            self.assertEqual(1, len(written_files))
            self.assertEqual(
                os.path.join(output_dir, "Beam_1_report_layers.csv"),
                written_files[0],
            )

            with open(written_files[0], "r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(1, len(rows))
        self.assertEqual("123456", rows[0]["patient_id"])
        self.assertEqual("Test^Patient", rows[0]["patient_name"])
        self.assertEqual("Beam / 1", rows[0]["beam_name"])
        self.assertEqual("7", rows[0]["beam_number"])
        self.assertEqual("1", rows[0]["layer_number"])
        self.assertEqual("filtered", rows[0]["report_mode_used"])
        self.assertEqual("True", rows[0]["layer_pass"])
        self.assertEqual("0.1", rows[0]["mean_diff_x_mm"])
        self.assertEqual("1", rows[0]["passed_spots"])
        self.assertEqual("1", rows[0]["total_spots"])

    def test_export_report_csv_uses_raw_sample_counts_for_raw_mode(self):
        report_data = {
            "Beam 2": {
                "beam_number": 2,
                "layers": [
                    {
                        "layer_index": 2,
                        "results": {
                            "diff_x": np.array([0.1, 0.2, 0.3]),
                            "diff_y": np.array([0.1, 0.2, 0.3]),
                            "assigned_spot_index": np.array([0, 0, 1]),
                            "mean_diff_x": 0.2,
                            "mean_diff_y": 0.2,
                            "std_diff_x": 0.1,
                            "std_diff_y": 0.1,
                            "rmse_x": 0.2,
                            "rmse_y": 0.2,
                            "max_abs_diff_x": 0.3,
                            "max_abs_diff_y": 0.3,
                            "p95_abs_diff_x": 0.3,
                            "p95_abs_diff_y": 0.3,
                            "settling_samples_count": 1,
                            "settling_status": "settled",
                        },
                    }
                ],
            },
        }

        with tempfile.TemporaryDirectory() as output_dir:
            written_files = export_report_csv(report_data, output_dir, report_mode="raw")
            with open(written_files[0], "r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(1, len(rows))
        self.assertEqual("2", rows[0]["layer_number"])
        self.assertEqual("3", rows[0]["num_total_samples"])
        self.assertEqual("2", rows[0]["num_included_samples"])
        self.assertEqual("0", rows[0]["num_filtered_samples"])
        self.assertEqual("2", rows[0]["total_spots"])
        self.assertEqual("2", rows[0]["passed_spots"])
