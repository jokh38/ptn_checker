import unittest
import os
import tempfile
import shutil
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
        self, filename, report_style="summary", save_debug_csv="off"
    ):
        with open(filename, "w", encoding="utf-8") as f:
            f.write("app:\n")
            f.write(f'  report_style: "{report_style}"\n')
            f.write(f'  save_debug_csv: "{save_debug_csv}"\n')

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
            self.yaml_config_path, report_style="classic"
        )

        with mock.patch.object(main, "generate_report") as mock_generate_report:
            run_analysis(self.test_dir, self.dcm_file, output_dir)

        self.assertEqual(
            mock_generate_report.call_args.kwargs["report_style"], "classic"
        )

    def test_run_analysis_writes_debug_csv_only_when_enabled(self):
        output_dir = os.path.join(self.test_dir, "output_debug")
        os.makedirs(output_dir)

        self.create_dummy_yaml_config_file(self.yaml_config_path, save_debug_csv="off")
        with mock.patch.object(main, "generate_report"):
            run_analysis(self.test_dir, self.dcm_file, output_dir)
        self.assertEqual(
            [],
            [name for name in os.listdir(output_dir) if name.endswith(".csv")],
        )

        self.create_dummy_yaml_config_file(self.yaml_config_path, save_debug_csv="on")
        with mock.patch.object(main, "generate_report"):
            run_analysis(self.test_dir, self.dcm_file, output_dir)
        self.assertTrue(any(name.endswith(".csv") for name in os.listdir(output_dir)))

    def test_run_analysis_writes_debug_csv_for_each_layer_when_enabled(self):
        output_dir = os.path.join(self.test_dir, "output_debug_all_layers")
        os.makedirs(output_dir)

        self.create_dummy_yaml_config_file(self.yaml_config_path, save_debug_csv="on")

        plan_data = {
            "patient_id": "123456",
            "patient_name": "Test^Patient",
            "machine_name": "G1",
            "beams": {
                1: {
                    "name": "Beam 1",
                    "layers": {
                        0: {"time_axis_s": np.array([0.0]), "trajectory_x_mm": np.array([0.0]), "trajectory_y_mm": np.array([0.0])},
                        1: {"time_axis_s": np.array([0.0]), "trajectory_x_mm": np.array([1.0]), "trajectory_y_mm": np.array([1.0])},
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

        with mock.patch.object(main, "parse_dcm_file", return_value=plan_data), mock.patch.object(
            main, "find_ptn_files", return_value=fake_ptn_files
        ), mock.patch.object(
            main, "parse_ptn_file", return_value={"time_ms": np.array([0.0]), "x": np.array([0.0]), "y": np.array([0.0])}
        ), mock.patch.object(
            main, "parse_planrange_for_directory", return_value={}
        ), mock.patch.object(
            main, "calculate_differences_for_layer", side_effect=fake_calculate_differences_for_layer
        ), mock.patch.object(main, "generate_report"):
            run_analysis(self.test_dir, self.dcm_file, output_dir)

        self.assertEqual(2, len(csv_calls))
        self.assertCountEqual(
            [
                os.path.join(output_dir, "debug_data_beam_1_layer_0.csv"),
                os.path.join(output_dir, "debug_data_beam_1_layer_1.csv"),
            ],
            csv_calls,
        )


if __name__ == "__main__":
    unittest.main()
