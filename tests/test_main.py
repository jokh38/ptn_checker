import unittest
import os
import tempfile
import shutil
import csv
from datetime import date
import numpy as np
from unittest import mock

import main
from tests.conftest import create_dummy_dcm_file
from main import find_ptn_files, run_analysis


class TestMain(unittest.TestCase):
    def setUp(self):
        """Set up a temporary directory with nested subdirectories and files."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(os.getcwd(), "scv_init_G1.txt")
        self.yaml_config_path = os.path.join(os.getcwd(), "config.yaml")
        self.original_config_contents = None
        self.original_yaml_config_contents = None
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.original_config_contents = f.read()
        if os.path.exists(self.yaml_config_path):
            with open(self.yaml_config_path, "r", encoding="utf-8") as f:
                self.original_yaml_config_contents = f.read()
        self.sub_dir = os.path.join(self.test_dir, "subdir1")
        self.nested_sub_dir = os.path.join(self.sub_dir, "subdir2")
        os.makedirs(self.nested_sub_dir)

        self.ptn_files = [
            os.path.join(self.test_dir, "file1.ptn"),
            os.path.join(self.sub_dir, "file2.ptn"),
            os.path.join(self.nested_sub_dir, "file3.ptn"),
        ]

        for ptn_file in self.ptn_files:
            # Create proper binary PTN files (10 spots * 8 shorts/spot = 80 shorts)
            dummy_ptn_data = np.arange(80, dtype=">u2")
            # Set beam_on_off values to 1 (positions 7, 15, 23, 31, 39, 47, 55, 63, 71, 79)
            for i in range(10):
                dummy_ptn_data[i * 8 + 7] = (
                    50000  # beam_on_off > 49152 threshold for Beam On
                )
            dummy_ptn_data.tofile(ptn_file)

        # Create a non-ptn file to ensure it's not picked up
        with open(os.path.join(self.test_dir, "not_a_ptn.txt"), "w") as f:
            f.write("some other data")

        # Create a dummy DICOM file
        self.dcm_file = os.path.join(self.test_dir, "test.dcm")
        create_dummy_dcm_file(self.dcm_file, "G1")

        # Create dummy config files in the root (or where main.py expects them)
        self.create_dummy_config_file(self.config_path)
        self.create_dummy_yaml_config_file(self.yaml_config_path)

    def tearDown(self):
        """Remove the temporary directory and its contents."""
        shutil.rmtree(self.test_dir)
        if self.original_config_contents is None:
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
        else:
            with open(self.config_path, "w", encoding="utf-8") as f:
                f.write(self.original_config_contents)
        if self.original_yaml_config_contents is None:
            if os.path.exists(self.yaml_config_path):
                os.remove(self.yaml_config_path)
        else:
            with open(self.yaml_config_path, "w", encoding="utf-8") as f:
                f.write(self.original_yaml_config_contents)

    def create_dummy_config_file(self, filename):
        with open(filename, "w") as f:
            f.write("XPOSGAIN\t1.0\n")
            f.write("YPOSGAIN\t1.0\n")
            f.write("XPOSOFFSET\t0.0\n")
            f.write("YPOSOFFSET\t0.0\n")
            f.write("TIMEGAIN\t0.001\n")
            f.write("SETTLING_THRESHOLD_MM\t0.5\n")
            f.write("SETTLING_WINDOW_SAMPLES\t10\n")
            f.write("SETTLING_CONSECUTIVE_SAMPLES\t3\n")

    def create_dummy_yaml_config_file(
        self,
        filename,
        report_style_summary=True,
        export_pdf_report=True,
        export_report_csv=False,
        save_debug_csv=False,
        report_detail_pdf=False,
        zero_dose_enabled=False,
        zero_dose_report_mode="filtered",
    ):
        with open(filename, "w", encoding="utf-8") as f:
            f.write("app:\n")
            f.write(
                f"  report_style_summary: {'true' if report_style_summary else 'false'}\n"
            )
            f.write(
                f"  export_pdf_report: {'true' if export_pdf_report else 'false'}\n"
            )
            f.write(
                f"  export_report_csv: {'true' if export_report_csv else 'false'}\n"
            )
            f.write(
                f"  save_debug_csv: {'true' if save_debug_csv else 'false'}\n"
            )
            f.write(
                f"  report_detail_pdf: {'true' if report_detail_pdf else 'false'}\n"
            )
            f.write("zero_dose_filter:\n")
            f.write(f"  enabled: {'true' if zero_dose_enabled else 'false'}\n")
            f.write(f'  report_mode: "{zero_dose_report_mode}"\n')

    def test_find_ptn_files(self):
        """
        Test that find_ptn_files correctly finds all .ptn files recursively.
        """
        found_files = find_ptn_files(self.test_dir)
        self.assertEqual(len(self.ptn_files), len(found_files))
        self.assertCountEqual(self.ptn_files, found_files)

    def test_run_analysis_dcm_not_found(self):
        """
        Test that run_analysis raises FileNotFoundError for a missing DICOM file.
        """
        with self.assertRaisesRegex(FileNotFoundError, "DICOM file not found"):
            run_analysis(self.test_dir, "non_existent.dcm", "report.pdf")

    def test_run_analysis_no_ptn_files_found(self):
        """
        Test that run_analysis raises FileNotFoundError when no .ptn files are found.
        """
        empty_dir = os.path.join(self.test_dir, "empty_dir")
        os.makedirs(empty_dir)
        with self.assertRaisesRegex(FileNotFoundError, "No .ptn files found"):
            run_analysis(empty_dir, self.dcm_file, "report.pdf")

    def test_run_analysis_integration(self):
        """
        Test that run_analysis can process DICOM and PTN files successfully.
        """
        output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(output_dir)

        # Should run without throwing the "No analysis results were generated" error
        try:
            run_analysis(self.test_dir, self.dcm_file, output_dir)
        except ValueError as e:
            if "No analysis results were generated" in str(e):
                self.fail(
                    "run_analysis failed with 'No analysis results were generated' - structure mismatch issue"
                )

    def test_run_analysis_uses_app_config_report_style(self):
        output_dir = os.path.join(self.test_dir, "output_style")
        os.makedirs(output_dir)
        self.create_dummy_yaml_config_file(
            self.yaml_config_path, report_style_summary=False
        )

        with mock.patch.object(main, "generate_report") as mock_generate_report:
            run_analysis(self.test_dir, self.dcm_file, output_dir)

        self.assertEqual(
            mock_generate_report.call_args.kwargs["report_style"], "classic"
        )

    def test_run_analysis_writes_debug_csv_only_when_enabled(self):
        output_dir = os.path.join(self.test_dir, "output_debug")
        os.makedirs(output_dir)

        self.create_dummy_yaml_config_file(self.yaml_config_path, save_debug_csv=False)
        with mock.patch.object(main, "generate_report"):
            run_analysis(self.test_dir, self.dcm_file, output_dir)
        self.assertEqual(
            [],
            [name for name in os.listdir(output_dir) if name.endswith(".csv")],
        )

        self.create_dummy_yaml_config_file(self.yaml_config_path, save_debug_csv=True)
        with mock.patch.object(main, "generate_report"):
            run_analysis(self.test_dir, self.dcm_file, output_dir)
        self.assertTrue(any(name.endswith(".csv") for name in os.listdir(output_dir)))

    def test_run_analysis_writes_debug_csv_for_each_layer_when_enabled(self):
        output_dir = os.path.join(self.test_dir, "output_debug_all_layers")
        os.makedirs(output_dir)

        self.create_dummy_yaml_config_file(self.yaml_config_path, save_debug_csv=True)

        plan_data = {
            "patient_id": "123456",
            "patient_name": "Test^Patient",
            "machine_name": "G1",
            "beams": {
                1: {
                    "name": "Beam 1",
                    "layers": {
                        0: {"time_axis_s": np.array([0.0]), "trajectory_x_mm": np.array([0.0]), "trajectory_y_mm": np.array([0.0])},
                        2: {"time_axis_s": np.array([0.0]), "trajectory_x_mm": np.array([1.0]), "trajectory_y_mm": np.array([1.0])},
                    },
                }
            },
        }
        fake_ptn_files = [
            os.path.join(self.test_dir, "layer0.ptn"),
            os.path.join(self.test_dir, "layer1.ptn"),
        ]
        csv_calls = []

        def fake_calculate_differences_for_layer(
            plan_layer,
            log_data,
            save_to_csv=False,
            csv_filename="",
            config=None,
        ):
            if save_to_csv:
                csv_calls.append(csv_filename)
                with open(csv_filename, "w", encoding="utf-8") as handle:
                    handle.write("header\n")
            return {
                "diff_x": np.array([0.0]),
                "diff_y": np.array([0.0]),
                "mean_diff_x": 0.0,
                "mean_diff_y": 0.0,
                "std_diff_x": 0.0,
                "std_diff_y": 0.0,
                "rmse_x": 0.0,
                "rmse_y": 0.0,
                "max_abs_diff_x": 0.0,
                "max_abs_diff_y": 0.0,
                "p95_abs_diff_x": 0.0,
                "p95_abs_diff_y": 0.0,
                "plan_positions": np.array([[0.0, 0.0]]),
                "log_positions": np.array([[0.0, 0.0]]),
                "hist_fit_x": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
                "hist_fit_y": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
                "time_overlap_fraction": 1.0,
                "is_settling": np.array([False]),
                "settling_index": 0,
                "settling_samples_count": 0,
                "settling_status": "settled",
            }

        with mock.patch.object(main, "load_plan_and_machine_config", return_value=(plan_data, {})), mock.patch.object(
            main, "find_ptn_files", return_value=fake_ptn_files
        ), mock.patch.object(
            main, "parse_ptn_with_optional_mu_correction", return_value={"time_ms": np.array([0.0]), "x": np.array([0.0]), "y": np.array([0.0])}
        ), mock.patch.object(
            main, "parse_planrange_for_directory", return_value={}
        ), mock.patch.object(
            main, "calculate_differences_for_layer", side_effect=fake_calculate_differences_for_layer
        ), mock.patch.object(main, "generate_report"):
            run_analysis(self.test_dir, self.dcm_file, output_dir)

        self.assertEqual(2, len(csv_calls))
        self.assertCountEqual(
            [
                os.path.join(output_dir, "debug_data_beam_1_layer_1.csv"),
                os.path.join(output_dir, "debug_data_beam_1_layer_2.csv"),
            ],
            csv_calls,
        )

    def test_run_analysis_passes_zero_dose_config_to_calculator(self):
        output_dir = os.path.join(self.test_dir, "output_zero_dose")
        os.makedirs(output_dir)
        self.create_dummy_yaml_config_file(
            self.yaml_config_path,
            zero_dose_enabled=True,
            zero_dose_report_mode="filtered",
        )

        captured_configs = []

        def fake_calculate_differences_for_layer(
            plan_layer,
            log_data,
            save_to_csv=False,
            csv_filename="",
            config=None,
        ):
            captured_configs.append(config)
            return {
                "diff_x": np.array([0.0]),
                "diff_y": np.array([0.0]),
                "mean_diff_x": 0.0,
                "mean_diff_y": 0.0,
                "std_diff_x": 0.0,
                "std_diff_y": 0.0,
                "rmse_x": 0.0,
                "rmse_y": 0.0,
                "max_abs_diff_x": 0.0,
                "max_abs_diff_y": 0.0,
                "p95_abs_diff_x": 0.0,
                "p95_abs_diff_y": 0.0,
                "plan_positions": np.array([[0.0, 0.0]]),
                "log_positions": np.array([[0.0, 0.0]]),
                "hist_fit_x": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
                "hist_fit_y": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
                "time_overlap_fraction": 1.0,
                "is_settling": np.array([False]),
                "settling_index": 0,
                "settling_samples_count": 0,
                "settling_status": "settled",
            }

        with mock.patch.object(main, "calculate_differences_for_layer", side_effect=fake_calculate_differences_for_layer), mock.patch.object(
            main, "generate_report"
        ):
            run_analysis(self.test_dir, self.dcm_file, output_dir)

        self.assertTrue(captured_configs)
        self.assertTrue(captured_configs[0]["ZERO_DOSE_FILTER_ENABLED"])
        self.assertEqual(captured_configs[0]["ZERO_DOSE_REPORT_MODE"], "filtered")

    def test_run_analysis_routes_gamma_mode_to_gamma_calculator(self):
        output_dir = os.path.join(self.test_dir, "output_gamma")
        os.makedirs(output_dir)

        plan_data = {
            "patient_id": "123456",
            "patient_name": "Test^Gamma",
            "machine_name": "G1",
            "beams": {
                1: {
                    "name": "Beam 1",
                    "layers": {
                        0: {
                            "time_axis_s": np.array([0.0]),
                            "trajectory_x_mm": np.array([0.0]),
                            "trajectory_y_mm": np.array([0.0]),
                            "positions": np.array([[0.0, 0.0]]),
                            "mu": np.array([1.0]),
                            "cumulative_mu": np.array([1.0]),
                            "spot_is_transit_min_dose": np.array([False]),
                        }
                    },
                }
            },
        }

        gamma_config = {
            "REPORT_STYLE_SUMMARY": True,
            "REPORT_STYLE": "summary",
            "EXPORT_PDF_REPORT": False,
            "EXPORT_REPORT_CSV": False,
            "SAVE_DEBUG_CSV": False,
            "ZERO_DOSE_REPORT_MODE": "filtered",
            "ANALYSIS_MODE": "point_gamma",
            "GAMMA_FLUENCE_PERCENT_THRESHOLD": 3.0,
            "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
            "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            "GAMMA_REQUIRE_PLANRANGE_MU_CORRECTION": True,
            "GAMMA_ALLOW_RELATIVE_FLUENCE_FALLBACK": False,
        }

        gamma_results = {
            "pass_rate": 100.0,
            "gamma_mean": 0.0,
            "gamma_max": 0.0,
            "evaluated_point_count": 1,
            "gamma_map": np.array([[0.0]]),
            "plan_positions": np.array([[0.0, 0.0]]),
            "log_positions": np.array([[0.0, 0.0]]),
            "plan_grid": np.array([[0.0]]),
            "log_grid": np.array([[0.0]]),
            "position_error_mean_mm": 0.0,
            "count_error_mean": 0.0,
            "normalization_mode": "point_gamma",
            "used_planrange_mu_correction": False,
            "unmatched_delivered_weight": 0.0,
        }

        def forbidden_trajectory_calculator(*args, **kwargs):
            self.fail("Gamma mode should not call the trajectory calculator")

        gamma_calculator_mock = mock.Mock(return_value=gamma_results)

        with mock.patch.object(
            main, "parse_yaml_config", return_value=gamma_config
        ), mock.patch.object(
            main, "load_plan_and_machine_config", return_value=(plan_data, {})
        ), mock.patch.object(
            main, "collect_ptn_delivery_groups",
            return_value=[
                {
                    "source_dir": self.test_dir,
                    "ptn_files": [os.path.join(self.test_dir, "gamma_layer.ptn")],
                    "planrange_lookup": {},
                    "beam_number": 1,
                }
            ],
        ), mock.patch.object(
            main,
            "parse_ptn_with_optional_mu_correction",
            return_value={"time_ms": np.array([0.0]), "x": np.array([0.0]), "y": np.array([0.0])},
        ), mock.patch.object(
            main,
            "calculate_differences_for_layer",
            side_effect=forbidden_trajectory_calculator,
        ), mock.patch.object(
            main,
            "calculate_point_gamma_for_layer",
            gamma_calculator_mock,
            create=True,
        ), mock.patch.object(main, "generate_report"):
            run_analysis(self.test_dir, self.dcm_file, output_dir)

        self.assertEqual(1, gamma_calculator_mock.call_count)

    def test_run_analysis_routes_point_gamma_mode_to_point_gamma_calculator(self):
        output_dir = os.path.join(self.test_dir, "output_point_gamma")
        os.makedirs(output_dir)

        plan_data = {
            "patient_id": "123456",
            "patient_name": "Test^PointGamma",
            "machine_name": "G1",
            "beams": {
                1: {
                    "name": "Beam 1",
                    "layers": {
                        0: {
                            "time_axis_s": np.array([0.0, 0.00012, 0.00024]),
                            "trajectory_x_mm": np.array([0.0, 2.0, 4.0]),
                            "trajectory_y_mm": np.array([0.0, 0.0, 0.0]),
                            "cumulative_mu": np.array([0.0, 2.0, 4.0]),
                        }
                    },
                }
            },
        }

        point_gamma_config = {
            "REPORT_STYLE_SUMMARY": True,
            "REPORT_STYLE": "summary",
            "EXPORT_PDF_REPORT": True,
            "EXPORT_REPORT_CSV": True,
            "SAVE_DEBUG_CSV": False,
            "REPORT_DETAIL_PDF": False,
            "ZERO_DOSE_REPORT_MODE": "filtered",
            "ANALYSIS_MODE": "point_gamma",
            "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
            "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
            "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            "GAMMA_REQUIRE_PLANRANGE_MU_CORRECTION": True,
            "GAMMA_ALLOW_RELATIVE_FLUENCE_FALLBACK": False,
            "GAMMA_NORMALIZATION_FACTOR_BY_MACHINE": {"G1": 5.5e-7, "G2": 5.0e-7},
        }

        point_gamma_results = {
            "pass_rate": 100.0,
            "gamma_mean": 0.0,
            "gamma_max": 0.0,
            "evaluated_point_count": 3,
            "gamma_map": np.array([[0.0, 0.0], [0.0, 0.0]]),
            "plan_grid": np.array([[0.0, 1.0], [2.0, 3.0]]),
            "log_grid": np.array([[0.0, 1.0], [2.0, 3.0]]),
            "normalization_mode": "point_gamma",
            "used_planrange_mu_correction": False,
            "unmatched_delivered_weight": 0.0,
        }

        point_gamma_calculator_mock = mock.Mock(return_value=point_gamma_results)

        with mock.patch.object(
            main, "parse_yaml_config", return_value=point_gamma_config
        ), mock.patch.object(
            main, "load_plan_and_machine_config", return_value=(plan_data, {})
        ), mock.patch.object(
            main, "collect_ptn_delivery_groups",
            return_value=[
                {
                    "source_dir": self.test_dir,
                    "ptn_files": [os.path.join(self.test_dir, "point_gamma_layer.ptn")],
                    "planrange_lookup": {},
                    "beam_number": 1,
                }
            ],
        ), mock.patch.object(
            main,
            "parse_ptn_with_optional_mu_correction",
            return_value={
                "time_ms": np.array([0.0, 0.06, 0.12]),
                "x": np.array([0.0, 1.0, 2.0]),
                "y": np.array([0.0, 0.0, 0.0]),
                "dose1_au": np.array([0.0, 1.0, 1.0]),
            },
        ), mock.patch.object(
            main,
            "calculate_differences_for_layer",
            side_effect=lambda *args, **kwargs: self.fail(
                "point_gamma mode should not call the trajectory calculator"
            ),
        ), mock.patch.object(
            main,
            "calculate_point_gamma_for_layer",
            point_gamma_calculator_mock,
            create=True,
        ), mock.patch.object(
            main,
            "generate_report"
        ) as generate_report_mock, mock.patch.object(
            main,
            "export_report_csv",
            create=True,
        ) as csv_export_mock:
            run_analysis(
                self.test_dir,
                self.dcm_file,
                output_dir,
                report_name="point_gamma_case",
            )

        self.assertEqual(1, point_gamma_calculator_mock.call_count)
        self.assertEqual(1, generate_report_mock.call_count)
        csv_export_mock.assert_not_called()
        self.assertEqual(
            "point_gamma_case",
            generate_report_mock.call_args.kwargs["report_name"],
        )
        self.assertEqual(
            "point_gamma",
            generate_report_mock.call_args.kwargs["analysis_mode"],
        )
        self.assertFalse(
            generate_report_mock.call_args.kwargs["report_detail_pdf"]
        )

    def test_run_analysis_routes_point_gamma_mode_to_summary_and_detail_reports_when_enabled(self):
        output_dir = os.path.join(self.test_dir, "output_point_gamma_detail")
        os.makedirs(output_dir)

        plan_data = {
            "patient_id": "123456",
            "patient_name": "Test^PointGamma",
            "machine_name": "G1",
            "beams": {
                1: {
                    "name": "Beam 1",
                    "layers": {
                        0: {
                            "time_axis_s": np.array([0.0, 0.00012, 0.00024]),
                            "trajectory_x_mm": np.array([0.0, 2.0, 4.0]),
                            "trajectory_y_mm": np.array([0.0, 0.0, 0.0]),
                            "cumulative_mu": np.array([0.0, 2.0, 4.0]),
                        }
                    },
                }
            },
        }

        point_gamma_config = {
            "REPORT_STYLE_SUMMARY": True,
            "REPORT_STYLE": "summary",
            "EXPORT_PDF_REPORT": True,
            "EXPORT_REPORT_CSV": False,
            "SAVE_DEBUG_CSV": False,
            "REPORT_DETAIL_PDF": True,
            "ZERO_DOSE_REPORT_MODE": "filtered",
            "ANALYSIS_MODE": "point_gamma",
            "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
            "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
            "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            "GAMMA_REQUIRE_PLANRANGE_MU_CORRECTION": True,
            "GAMMA_ALLOW_RELATIVE_FLUENCE_FALLBACK": False,
            "GAMMA_NORMALIZATION_FACTOR_BY_MACHINE": {"G1": 5.5e-7, "G2": 5.0e-7},
        }

        point_gamma_results = {
            "pass_rate": 100.0,
            "gamma_mean": 0.0,
            "gamma_max": 0.0,
            "evaluated_point_count": 3,
            "gamma_map": np.array([[0.0, 0.0], [0.0, 0.0]]),
            "plan_grid": np.array([[0.0, 1.0], [2.0, 3.0]]),
            "log_grid": np.array([[0.0, 1.0], [2.0, 3.0]]),
            "normalization_mode": "point_gamma",
            "used_planrange_mu_correction": False,
            "unmatched_delivered_weight": 0.0,
        }

        point_gamma_calculator_mock = mock.Mock(return_value=point_gamma_results)

        with mock.patch.object(
            main, "parse_yaml_config", return_value=point_gamma_config
        ), mock.patch.object(
            main, "load_plan_and_machine_config", return_value=(plan_data, {})
        ), mock.patch.object(
            main, "collect_ptn_delivery_groups",
            return_value=[
                {
                    "source_dir": self.test_dir,
                    "ptn_files": [os.path.join(self.test_dir, "point_gamma_layer.ptn")],
                    "planrange_lookup": {},
                    "beam_number": 1,
                }
            ],
        ), mock.patch.object(
            main,
            "parse_ptn_with_optional_mu_correction",
            return_value={
                "time_ms": np.array([0.0, 0.06, 0.12]),
                "x": np.array([0.0, 1.0, 2.0]),
                "y": np.array([0.0, 0.0, 0.0]),
                "dose1_au": np.array([0.0, 1.0, 1.0]),
            },
        ), mock.patch.object(
            main,
            "calculate_differences_for_layer",
            side_effect=lambda *args, **kwargs: self.fail(
                "point_gamma mode should not call the trajectory calculator"
            ),
        ), mock.patch.object(
            main,
            "calculate_point_gamma_for_layer",
            point_gamma_calculator_mock,
            create=True,
        ), mock.patch.object(
            main,
            "generate_report",
        ) as generate_report_mock, mock.patch.object(
            main,
            "export_report_csv",
            create=True,
        ) as csv_export_mock:
            run_analysis(
                self.test_dir,
                self.dcm_file,
                output_dir,
                report_name="point_gamma_case",
            )

        self.assertEqual(1, point_gamma_calculator_mock.call_count)
        self.assertEqual(1, generate_report_mock.call_count)
        self.assertEqual("point_gamma_case", generate_report_mock.call_args.kwargs["report_name"])
        self.assertEqual(
            "point_gamma",
            generate_report_mock.call_args.kwargs["analysis_mode"],
        )
        self.assertTrue(generate_report_mock.call_args.kwargs["report_detail_pdf"])
        csv_export_mock.assert_not_called()

    def test_run_analysis_uses_machine_specific_gamma_normalization_factor(self):
        output_dir = os.path.join(self.test_dir, "output_gamma_factor")
        os.makedirs(output_dir)

        plan_data = {
            "patient_id": "123456",
            "patient_name": "Test^GammaFactor",
            "machine_name": "G2",
            "beams": {
                1: {
                    "name": "Beam 1",
                    "layers": {
                        0: {
                            "time_axis_s": np.array([0.0]),
                            "trajectory_x_mm": np.array([0.0]),
                            "trajectory_y_mm": np.array([0.0]),
                            "positions": np.array([[0.0, 0.0]]),
                            "mu": np.array([1.0]),
                            "cumulative_mu": np.array([1.0]),
                            "spot_is_transit_min_dose": np.array([False]),
                        }
                    },
                }
            },
        }

        gamma_config = {
            "REPORT_STYLE_SUMMARY": True,
            "REPORT_STYLE": "summary",
            "EXPORT_PDF_REPORT": False,
            "EXPORT_REPORT_CSV": False,
            "SAVE_DEBUG_CSV": False,
            "REPORT_DETAIL_PDF": False,
            "ZERO_DOSE_REPORT_MODE": "filtered",
            "ANALYSIS_MODE": "point_gamma",
            "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
            "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
            "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            "GAMMA_REQUIRE_PLANRANGE_MU_CORRECTION": True,
            "GAMMA_ALLOW_RELATIVE_FLUENCE_FALLBACK": False,
            "GAMMA_NORMALIZATION_FACTOR_BY_MACHINE": {"G1": 5.5e-7, "G2": 5.0e-7},
        }

        gamma_results = {
            "pass_rate": 100.0,
            "gamma_mean": 0.0,
            "gamma_max": 0.0,
            "evaluated_point_count": 1,
            "gamma_map": np.array([[0.0]]),
            "plan_positions": np.array([[0.0, 0.0]]),
            "log_positions": np.array([[0.0, 0.0]]),
            "plan_grid": np.array([[0.0]]),
            "log_grid": np.array([[0.0]]),
            "position_error_mean_mm": 0.0,
            "count_error_mean": 0.0,
            "normalization_mode": "point_gamma",
            "used_planrange_mu_correction": False,
            "unmatched_delivered_weight": 0.0,
        }

        gamma_calculator_mock = mock.Mock(return_value=gamma_results)

        with mock.patch.object(
            main, "parse_yaml_config", return_value=gamma_config
        ), mock.patch.object(
            main, "load_plan_and_machine_config", return_value=(plan_data, {})
        ), mock.patch.object(
            main, "collect_ptn_delivery_groups",
            return_value=[
                {
                    "source_dir": self.test_dir,
                    "ptn_files": [os.path.join(self.test_dir, "gamma_layer.ptn")],
                    "planrange_lookup": {},
                    "beam_number": 1,
                }
            ],
        ), mock.patch.object(
            main,
            "parse_ptn_with_optional_mu_correction",
            return_value={"time_ms": np.array([0.0]), "x": np.array([0.0]), "y": np.array([0.0])},
        ), mock.patch.object(
            main,
            "calculate_point_gamma_for_layer",
            gamma_calculator_mock,
            create=True,
        ), mock.patch.object(main, "generate_report"):
            run_analysis(self.test_dir, self.dcm_file, output_dir)

        passed_config = gamma_calculator_mock.call_args.args[2]
        self.assertEqual(5.0e-7, passed_config["GAMMA_NORMALIZATION_FACTOR"])

    def test_run_analysis_routes_gamma_mode_to_gamma_pdf_report(self):
        output_dir = os.path.join(self.test_dir, "output_gamma_pdf")
        os.makedirs(output_dir)

        plan_data = {
            "patient_id": "123456",
            "patient_name": "Test^GammaPDF",
            "machine_name": "G1",
            "beams": {
                1: {
                    "name": "Beam 1",
                    "layers": {
                        0: {
                            "time_axis_s": np.array([0.0]),
                            "trajectory_x_mm": np.array([0.0]),
                            "trajectory_y_mm": np.array([0.0]),
                            "positions": np.array([[0.0, 0.0]]),
                            "mu": np.array([1.0]),
                            "cumulative_mu": np.array([1.0]),
                            "spot_is_transit_min_dose": np.array([False]),
                        }
                    },
                }
            },
        }

        gamma_config = {
            "REPORT_STYLE_SUMMARY": True,
            "REPORT_STYLE": "summary",
            "EXPORT_PDF_REPORT": True,
            "EXPORT_REPORT_CSV": False,
            "SAVE_DEBUG_CSV": False,
            "REPORT_DETAIL_PDF": True,
            "ZERO_DOSE_REPORT_MODE": "filtered",
            "ANALYSIS_MODE": "point_gamma",
            "GAMMA_FLUENCE_PERCENT_THRESHOLD": 3.0,
            "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
            "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            "GAMMA_REQUIRE_PLANRANGE_MU_CORRECTION": True,
            "GAMMA_ALLOW_RELATIVE_FLUENCE_FALLBACK": False,
        }

        gamma_results = {
            "pass_rate": 100.0,
            "gamma_mean": 0.0,
            "gamma_max": 0.0,
            "evaluated_point_count": 1,
            "gamma_map": np.array([[0.0]]),
            "plan_positions": np.array([[0.0, 0.0]]),
            "log_positions": np.array([[0.0, 0.0]]),
            "plan_grid": np.array([[0.0]]),
            "log_grid": np.array([[0.0]]),
            "position_error_mean_mm": 0.0,
            "count_error_mean": 0.0,
            "normalization_mode": "point_gamma",
            "used_planrange_mu_correction": False,
            "unmatched_delivered_weight": 0.0,
        }

        gamma_calculator_mock = mock.Mock(return_value=gamma_results)
        with mock.patch.object(
            main, "parse_yaml_config", return_value=gamma_config
        ), mock.patch.object(
            main, "load_plan_and_machine_config", return_value=(plan_data, {})
        ), mock.patch.object(
            main, "collect_ptn_delivery_groups",
            return_value=[
                {
                    "source_dir": self.test_dir,
                    "ptn_files": [os.path.join(self.test_dir, "gamma_layer.ptn")],
                    "planrange_lookup": {},
                    "beam_number": 1,
                }
            ],
        ), mock.patch.object(
            main,
            "parse_ptn_with_optional_mu_correction",
            return_value={"time_ms": np.array([0.0]), "x": np.array([0.0]), "y": np.array([0.0])},
        ), mock.patch.object(
            main,
            "calculate_point_gamma_for_layer",
            gamma_calculator_mock,
            create=True,
        ), mock.patch.object(main, "generate_report") as generate_report_mock:
            run_analysis(
                self.test_dir,
                self.dcm_file,
                output_dir,
                report_name="point_gamma_case",
            )

        self.assertEqual(1, generate_report_mock.call_count)
        self.assertEqual("point_gamma_case", generate_report_mock.call_args.kwargs["report_name"])
        self.assertEqual(
            "point_gamma",
            generate_report_mock.call_args.kwargs["analysis_mode"],
        )
        self.assertTrue(generate_report_mock.call_args.kwargs["report_detail_pdf"])

    def test_run_analysis_matches_single_delivery_to_beam_by_layer_count(self):
        log_dir = os.path.join(self.test_dir, "single_delivery")
        os.makedirs(log_dir)
        for idx in range(1, 35):
            open(os.path.join(log_dir, f"layer_{idx:03d}.ptn"), "wb").close()
        with open(os.path.join(log_dir, "PlanInfo.txt"), "w", encoding="utf-8") as handle:
            handle.write("DICOM_BEAM_NUMBER,3\n")

        output_dir = os.path.join(self.test_dir, "output_single_delivery")
        os.makedirs(output_dir)

        plan_data = {
            "patient_id": "123456",
            "patient_name": "Test^Patient",
            "machine_name": "G1",
            "beams": {
                2: {"name": "Beam 35", "layers": {i * 2: {"time_axis_s": np.array([0.0]), "trajectory_x_mm": np.array([0.0]), "trajectory_y_mm": np.array([0.0])} for i in range(35)}},
                3: {"name": "Beam 34", "layers": {i * 2: {"time_axis_s": np.array([0.0]), "trajectory_x_mm": np.array([0.0]), "trajectory_y_mm": np.array([0.0])} for i in range(34)}},
                4: {"name": "Beam 39", "layers": {i * 2: {"time_axis_s": np.array([0.0]), "trajectory_x_mm": np.array([0.0]), "trajectory_y_mm": np.array([0.0])} for i in range(39)}},
            },
        }

        processed_layers = []

        def fake_calculate_differences_for_layer(
            plan_layer,
            log_data,
            save_to_csv=False,
            csv_filename="",
            config=None,
        ):
            processed_layers.append(plan_layer)
            return {
                "diff_x": np.array([0.0]),
                "diff_y": np.array([0.0]),
                "mean_diff_x": 0.0,
                "mean_diff_y": 0.0,
                "std_diff_x": 0.0,
                "std_diff_y": 0.0,
                "rmse_x": 0.0,
                "rmse_y": 0.0,
                "max_abs_diff_x": 0.0,
                "max_abs_diff_y": 0.0,
                "p95_abs_diff_x": 0.0,
                "p95_abs_diff_y": 0.0,
                "plan_positions": np.array([[0.0, 0.0]]),
                "log_positions": np.array([[0.0, 0.0]]),
                "hist_fit_x": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
                "hist_fit_y": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
                "time_overlap_fraction": 1.0,
                "is_settling": np.array([False]),
                "settling_index": 0,
                "settling_samples_count": 0,
                "settling_status": "settled",
            }

        with mock.patch.object(main, "load_plan_and_machine_config", return_value=(plan_data, {})), mock.patch.object(
            main, "parse_ptn_with_optional_mu_correction", return_value={"time_ms": np.array([0.0]), "x": np.array([0.0]), "y": np.array([0.0])}
        ), mock.patch.object(
            main, "parse_planrange_for_directory", return_value={}
        ), mock.patch.object(
            main, "calculate_differences_for_layer", side_effect=fake_calculate_differences_for_layer
        ), mock.patch.object(main, "generate_report") as mock_generate_report:
            run_analysis(log_dir, self.dcm_file, output_dir, report_name="single_delivery")

        self.assertEqual(34, len(processed_layers))
        report_data = mock_generate_report.call_args.args[0]
        self.assertEqual(0, len(report_data["Beam 35"]["layers"]))
        self.assertEqual(34, len(report_data["Beam 34"]["layers"]))
        self.assertEqual(0, len(report_data["Beam 39"]["layers"]))

    def test_run_analysis_combines_day_deliveries_into_one_report_in_chronological_order(self):
        day_dir = os.path.join(self.test_dir, "0722")
        os.makedirs(day_dir)
        delivery_specs = [
            ("2025072222131300", 34, 3),
            ("2025072222175500", 35, 2),
            ("2025072222232700", 39, 4),
        ]
        for dirname, count, beam_number in delivery_specs:
            delivery_dir = os.path.join(day_dir, dirname)
            os.makedirs(delivery_dir)
            for idx in range(1, count + 1):
                open(os.path.join(delivery_dir, f"layer_{idx:03d}.ptn"), "wb").close()
            with open(os.path.join(delivery_dir, "PlanInfo.txt"), "w", encoding="utf-8") as handle:
                handle.write(f"DICOM_BEAM_NUMBER,{beam_number}\n")

        output_dir = os.path.join(self.test_dir, "output_day")
        os.makedirs(output_dir)

        plan_data = {
            "patient_id": "123456",
            "patient_name": "Test^Patient",
            "machine_name": "G1",
            "beams": {
                2: {"name": "Beam A", "layers": {i * 2: {"time_axis_s": np.array([0.0]), "trajectory_x_mm": np.array([0.0]), "trajectory_y_mm": np.array([0.0])} for i in range(35)}},
                3: {"name": "Beam B", "layers": {i * 2: {"time_axis_s": np.array([0.0]), "trajectory_x_mm": np.array([0.0]), "trajectory_y_mm": np.array([0.0])} for i in range(34)}},
                4: {"name": "Beam C", "layers": {i * 2: {"time_axis_s": np.array([0.0]), "trajectory_x_mm": np.array([0.0]), "trajectory_y_mm": np.array([0.0])} for i in range(39)}},
            },
        }

        parsed_files = []

        def fake_parse_ptn_file(file_path, config, planrange_lookup):
            parsed_files.append(file_path)
            return {"time_ms": np.array([0.0]), "x": np.array([0.0]), "y": np.array([0.0])}

        def fake_calculate_differences_for_layer(
            plan_layer,
            log_data,
            save_to_csv=False,
            csv_filename="",
            config=None,
        ):
            return {
                "diff_x": np.array([0.0]),
                "diff_y": np.array([0.0]),
                "mean_diff_x": 0.0,
                "mean_diff_y": 0.0,
                "std_diff_x": 0.0,
                "std_diff_y": 0.0,
                "rmse_x": 0.0,
                "rmse_y": 0.0,
                "max_abs_diff_x": 0.0,
                "max_abs_diff_y": 0.0,
                "p95_abs_diff_x": 0.0,
                "p95_abs_diff_y": 0.0,
                "plan_positions": np.array([[0.0, 0.0]]),
                "log_positions": np.array([[0.0, 0.0]]),
                "hist_fit_x": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
                "hist_fit_y": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
                "time_overlap_fraction": 1.0,
                "is_settling": np.array([False]),
                "settling_index": 0,
                "settling_samples_count": 0,
                "settling_status": "settled",
            }

        with mock.patch.object(main, "load_plan_and_machine_config", return_value=(plan_data, {})), mock.patch.object(
            main, "parse_ptn_with_optional_mu_correction", side_effect=fake_parse_ptn_file
        ), mock.patch.object(
            main, "parse_planrange_for_directory", return_value={}
        ), mock.patch.object(
            main, "calculate_differences_for_layer", side_effect=fake_calculate_differences_for_layer
        ), mock.patch.object(main, "generate_report") as mock_generate_report:
            run_analysis(day_dir, self.dcm_file, output_dir, report_name="combined_day")

        mock_generate_report.assert_called_once()
        self.assertEqual("combined_day", mock_generate_report.call_args.kwargs["report_name"])
        report_data = mock_generate_report.call_args.args[0]
        self.assertEqual(["Beam B", "Beam A", "Beam C"], [key for key in report_data if not key.startswith("_")])
        self.assertEqual(35, len(report_data["Beam A"]["layers"]))
        self.assertEqual(34, len(report_data["Beam B"]["layers"]))
        self.assertEqual(39, len(report_data["Beam C"]["layers"]))

        self.assertTrue(parsed_files[0].startswith(os.path.join(day_dir, "2025072222131300")))
        self.assertTrue(parsed_files[34].startswith(os.path.join(day_dir, "2025072222175500")))
        self.assertTrue(parsed_files[69].startswith(os.path.join(day_dir, "2025072222232700")))

    def test_run_analysis_writes_report_csv_without_pdf_when_enabled(self):
        output_dir = os.path.join(self.test_dir, "output_report_csv")
        os.makedirs(output_dir)
        self.create_dummy_yaml_config_file(
            self.yaml_config_path,
            report_style_summary=True,
            export_pdf_report=False,
            export_report_csv=True,
            save_debug_csv=False,
            zero_dose_enabled=True,
            zero_dose_report_mode="filtered",
        )

        plan_data = {
            "patient_id": "123456",
            "patient_name": "Test^Patient",
            "machine_name": "G1",
            "beams": {
                1: {
                    "name": "Beam 1",
                    "layers": {
                        0: {
                            "time_axis_s": np.array([0.0]),
                            "trajectory_x_mm": np.array([0.0]),
                            "trajectory_y_mm": np.array([0.0]),
                        },
                        2: {
                            "time_axis_s": np.array([0.0]),
                            "trajectory_x_mm": np.array([1.0]),
                            "trajectory_y_mm": np.array([1.0]),
                        },
                    },
                }
            },
        }
        fake_ptn_files = [
            os.path.join(self.test_dir, "layer0.ptn"),
            os.path.join(self.test_dir, "layer1.ptn"),
        ]

        results_queue = [
            {
                "diff_x": np.array([0.1, 0.2]),
                "diff_y": np.array([0.1, 0.2]),
                "filtered_diff_x": np.array([0.1]),
                "filtered_diff_y": np.array([0.1]),
                "sample_is_included_filtered_stats": np.array([True, False]),
                "assigned_spot_index": np.array([0, 0]),
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
                "num_included_samples": 1,
                "num_filtered_samples": 1,
                "filtered_sample_fraction": 0.5,
                "filtered_mu_fraction_estimate": 0.25,
                "time_overlap_fraction": 1.0,
                "is_settling": np.array([False, False]),
                "settling_index": 0,
                "settling_samples_count": 0,
                "settling_status": "settled",
                "plan_positions": np.array([[0.0, 0.0]]),
                "log_positions": np.array([[0.0, 0.0]]),
                "hist_fit_x": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
                "hist_fit_y": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
            },
            {
                "diff_x": np.array([0.2, 0.3]),
                "diff_y": np.array([0.2, 0.3]),
                "assigned_spot_index": np.array([0, 1]),
                "mean_diff_x": 0.2,
                "mean_diff_y": 0.3,
                "std_diff_x": 0.4,
                "std_diff_y": 0.5,
                "rmse_x": 0.6,
                "rmse_y": 0.7,
                "max_abs_diff_x": 0.8,
                "max_abs_diff_y": 0.9,
                "p95_abs_diff_x": 1.0,
                "p95_abs_diff_y": 1.1,
                "filtered_mean_diff_x": 0.2,
                "filtered_mean_diff_y": 0.3,
                "filtered_std_diff_x": 0.4,
                "filtered_std_diff_y": 0.5,
                "filtered_rmse_x": 0.6,
                "filtered_rmse_y": 0.7,
                "filtered_max_abs_diff_x": 0.8,
                "filtered_max_abs_diff_y": 0.9,
                "filtered_p95_abs_diff_x": 1.0,
                "filtered_p95_abs_diff_y": 1.1,
                "filtered_stats_fallback_to_raw": True,
                "num_included_samples": 0,
                "num_filtered_samples": 2,
                "filtered_sample_fraction": 1.0,
                "filtered_mu_fraction_estimate": 1.0,
                "time_overlap_fraction": 0.75,
                "is_settling": np.array([False, True]),
                "settling_index": 1,
                "settling_samples_count": 1,
                "settling_status": "never_settled",
                "plan_positions": np.array([[1.0, 1.0]]),
                "log_positions": np.array([[1.0, 1.0]]),
                "hist_fit_x": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
                "hist_fit_y": {"amplitude": 0.0, "mean": 0.0, "stddev": 0.0},
            },
        ]

        def fake_calculate_differences_for_layer(
            plan_layer,
            log_data,
            save_to_csv=False,
            csv_filename="",
            config=None,
        ):
            return results_queue.pop(0)

        with mock.patch.object(main, "load_plan_and_machine_config", return_value=(plan_data, {})), mock.patch.object(
            main, "find_ptn_files", return_value=fake_ptn_files
        ), mock.patch.object(
            main, "parse_ptn_with_optional_mu_correction", return_value={"time_ms": np.array([0.0]), "x": np.array([0.0]), "y": np.array([0.0])}
        ), mock.patch.object(
            main, "parse_planrange_for_directory", return_value={}
        ), mock.patch.object(
            main, "calculate_differences_for_layer", side_effect=fake_calculate_differences_for_layer
        ), mock.patch.object(main, "generate_report") as mock_generate_report:
            run_analysis(self.test_dir, self.dcm_file, output_dir)

        mock_generate_report.assert_not_called()
        csv_files = sorted(name for name in os.listdir(output_dir) if name.endswith(".csv"))
        self.assertEqual(["Beam_1_report_layers.csv"], csv_files)

        csv_path = os.path.join(output_dir, csv_files[0])
        with open(csv_path, "r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(2, len(rows))
        self.assertEqual("1", rows[0]["layer_number"])
        self.assertEqual("2", rows[1]["layer_number"])
        self.assertEqual("filtered", rows[0]["report_mode_used"])
        self.assertEqual("True", rows[0]["layer_pass"])
        self.assertEqual("False", rows[0]["filtered_stats_fallback_to_raw"])
        self.assertEqual("0.1", rows[0]["mean_diff_x_mm"])
        self.assertEqual("2", rows[0]["num_total_samples"])
        self.assertEqual("1", rows[0]["passed_spots"])
        self.assertEqual("1", rows[0]["total_spots"])
        self.assertEqual("True", rows[1]["filtered_stats_fallback_to_raw"])
        self.assertEqual("0.75", rows[1]["time_overlap_fraction"])

    def test_main_uses_parent_case_directory_name_for_combined_report(self):
        case_dir = os.path.join(self.test_dir, "55758663")
        os.makedirs(case_dir)

        with mock.patch.object(main, "run_analysis") as mock_run_analysis, mock.patch(
            "sys.argv",
            [
                "main.py",
                "--log_dir",
                case_dir,
                "--dcm_file",
                self.dcm_file,
                "--output",
                self.test_dir,
            ],
        ):
            main.main()

        expected_report_name = f"55758663_{date.today().isoformat()}"
        self.assertEqual(
            mock.call(case_dir, self.dcm_file, self.test_dir, report_name=expected_report_name),
            mock_run_analysis.call_args,
        )

    def test_run_analysis_passes_analysis_config_to_generate_report(self):
        output_dir = os.path.join(self.test_dir, "output_config_pass")
        os.makedirs(output_dir)
        self.create_dummy_yaml_config_file(self.yaml_config_path, zero_dose_enabled=True)

        with mock.patch.object(main, "generate_report") as mock_generate_report:
            run_analysis(self.test_dir, self.dcm_file, output_dir)

        self.assertIn("analysis_config", mock_generate_report.call_args.kwargs)
        passed_config = mock_generate_report.call_args.kwargs["analysis_config"]
        self.assertIsNotNone(passed_config)
        self.assertIn("SETTLING_THRESHOLD_MM", passed_config)
        self.assertTrue(passed_config["ZERO_DOSE_FILTER_ENABLED"])

    def test_derive_report_name_uses_case_directory_basename(self):
        report_name = main.derive_report_name("/tmp/55758663")
        self.assertEqual(f"55758663_{date.today().isoformat()}", report_name)


if __name__ == "__main__":
    unittest.main()
