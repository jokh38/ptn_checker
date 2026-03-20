import os
import tempfile
import unittest
import numpy as np
from src.calculator import calculate_differences_for_layer


class TestCalculator(unittest.TestCase):
    def test_calculator_uses_time_axis_for_plan_sampling(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 1.0, 2.0]),
            "trajectory_x_mm": np.array([0.0, 0.0, 10.0]),
            "trajectory_y_mm": np.array([0.0, 0.0, 0.0]),
        }
        log_data = {
            "time_ms": np.array([0.0, 500.0, 1000.0, 1500.0, 2000.0]),
            "x": np.array([0.0, 0.0, 0.0, 5.0, 10.0]),
            "y": np.array([0.0, 0.0, 0.0, 0.0, 0.0]),
        }
        results = calculate_differences_for_layer(plan_layer, log_data)
        self.assertTrue(np.allclose(results["diff_x"], 0.0))

    def test_calculator_errors_when_time_axis_is_missing(self):
        results = calculate_differences_for_layer(
            {"positions": np.zeros((2, 2))},
            {"x": np.array([])},
        )
        self.assertIn("error", results)

    def test_calculator_result_keys(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 1.0]),
            "trajectory_x_mm": np.array([0.0, 5.0]),
            "trajectory_y_mm": np.array([0.0, 5.0]),
        }
        log_data = {
            "time_ms": np.array([0.0, 500.0, 1000.0]),
            "x": np.array([0.0, 2.5, 5.0]),
            "y": np.array([0.0, 2.5, 5.0]),
        }
        results = calculate_differences_for_layer(plan_layer, log_data)
        for key in (
            'diff_x', 'diff_y', 'mean_diff_x', 'mean_diff_y',
            'std_diff_x', 'std_diff_y', 'rmse_x', 'rmse_y',
            'max_abs_diff_x', 'max_abs_diff_y', 'p95_abs_diff_x',
            'p95_abs_diff_y', 'plan_positions', 'log_positions',
            'hist_fit_x', 'hist_fit_y',
        ):
            self.assertIn(key, results, f"Missing key: {key}")

    def test_calculator_reports_time_overlap_fraction(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 1.0]),
            "trajectory_x_mm": np.array([0.0, 10.0]),
            "trajectory_y_mm": np.array([0.0, 0.0]),
        }
        log_data = {
            "time_ms": np.array([0.0, 500.0, 1000.0]),
            "x": np.array([0.0, 5.0, 10.0]),
            "y": np.array([0.0, 0.0, 0.0]),
        }
        results = calculate_differences_for_layer(plan_layer, log_data)
        self.assertTrue(np.isclose(results["time_overlap_fraction"], 1.0))

    def test_calculator_handles_out_of_histogram_range_differences(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 1.0]),
            "trajectory_x_mm": np.array([100.0, 110.0]),
            "trajectory_y_mm": np.array([100.0, 110.0]),
        }
        log_data = {
            "time_ms": np.array([0.0, 1000.0]),
            "x": np.array([0.0, 0.0]),
            "y": np.array([0.0, 0.0]),
        }
        results = calculate_differences_for_layer(plan_layer, log_data)
        hist_fit_x = results.get("hist_fit_x", {})
        hist_fit_y = results.get("hist_fit_y", {})
        self.assertTrue(np.isfinite(hist_fit_x.get("mean", np.nan)))
        self.assertTrue(np.isfinite(hist_fit_y.get("mean", np.nan)))

    def test_calculator_applies_settling_filter_by_default(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
            "trajectory_x_mm": np.array([0.0, 0.0, 0.0, 0.0, 0.0]),
            "trajectory_y_mm": np.array([0.0, 0.0, 0.0, 0.0, 0.0]),
        }
        log_data = {
            "time_ms": np.array([0.0, 0.2, 0.4, 0.6, 0.8]),
            "x": np.array([-1.0, -0.8, -0.2, -0.1, -0.1]),
            "y": np.array([-0.9, -0.7, -0.2, -0.1, -0.1]),
        }
        config = {
            "SETTLING_THRESHOLD_MM": 0.5,
            "SETTLING_WINDOW_SAMPLES": 5,
            "SETTLING_CONSECUTIVE_SAMPLES": 2,
        }

        results = calculate_differences_for_layer(plan_layer, log_data, config=config)

        np.testing.assert_array_equal(
            results["is_settling"],
            np.array([True, True, False, False, False]),
        )
        self.assertEqual(results["settling_index"], 2)
        self.assertEqual(results["settling_samples_count"], 2)
        self.assertEqual(results["settling_status"], "settled")
        self.assertAlmostEqual(results["mean_diff_x"], np.mean([0.2, 0.1, 0.1]))
        self.assertAlmostEqual(results["max_abs_diff_x"], 0.2)

    def test_calculator_starts_after_reaching_initial_plan_position(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
            "trajectory_x_mm": np.array([5.0, 10.0, 15.0, 20.0, 25.0]),
            "trajectory_y_mm": np.array([2.0, 2.0, 2.0, 2.0, 2.0]),
        }
        log_data = {
            "time_ms": np.array([0.0, 0.2, 0.4, 0.6, 0.8]),
            "x": np.array([-3.0, -2.0, 5.2, 15.0, 25.0]),
            "y": np.array([-4.0, -2.5, 2.1, 2.0, 2.0]),
        }
        config = {
            "SETTLING_THRESHOLD_MM": 0.5,
            "SETTLING_WINDOW_SAMPLES": 5,
            "SETTLING_CONSECUTIVE_SAMPLES": 1,
        }

        results = calculate_differences_for_layer(plan_layer, log_data, config=config)

        np.testing.assert_array_equal(
            results["is_settling"],
            np.array([True, True, False, False, False]),
        )
        self.assertEqual(results["settling_index"], 2)
        self.assertEqual(results["settling_status"], "settled")

    def test_calculator_uses_time_cap_for_initial_position_search(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 1.0, 2.0, 3.0]),
            "trajectory_x_mm": np.array([5.0, 6.0, 7.0, 8.0]),
            "trajectory_y_mm": np.array([2.0, 2.0, 2.0, 2.0]),
        }
        log_data = {
            "time_ms": np.array([0.0, 0.4, 0.8, 1.2]),
            "x": np.array([-3.0, 5.1, 7.0, 8.0]),
            "y": np.array([-3.0, 2.1, 2.0, 2.0]),
        }
        config = {
            "SETTLING_THRESHOLD_MM": 0.5,
            "SETTLING_WINDOW_SAMPLES": 1,
            "SETTLING_CONSECUTIVE_SAMPLES": 1,
        }

        results = calculate_differences_for_layer(plan_layer, log_data, config=config)

        np.testing.assert_array_equal(
            results["is_settling"],
            np.array([True, False, False, False]),
        )
        self.assertEqual(results["settling_index"], 1)
        self.assertEqual(results["settling_status"], "settled")

    def test_calculator_writes_settling_flag_to_csv(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 1.0, 2.0]),
            "trajectory_x_mm": np.array([0.0, 0.0, 0.0]),
            "trajectory_y_mm": np.array([0.0, 0.0, 0.0]),
            "cumulative_mu": np.array([1.0, 2.0, 3.0]),
        }
        log_data = {
            "time_ms": np.array([0.0, 0.3, 0.6]),
            "x": np.array([-0.8, -0.2, -0.1]),
            "y": np.array([-0.8, -0.2, -0.1]),
            "x_raw": np.array([1.0, 2.0, 3.0]),
            "y_raw": np.array([4.0, 5.0, 6.0]),
            "layer_num": np.array([7.0, 7.0, 7.0]),
            "beam_on_off": np.array([50000.0, 50000.0, 50000.0]),
            "mu": np.array([0.5, 1.5, 2.5]),
        }
        config = {
            "SETTLING_THRESHOLD_MM": 0.5,
            "SETTLING_WINDOW_SAMPLES": 3,
            "SETTLING_CONSECUTIVE_SAMPLES": 2,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "debug.csv")
            calculate_differences_for_layer(
                plan_layer,
                log_data,
                save_to_csv=True,
                csv_filename=csv_path,
                config=config,
            )

            csv_data = np.genfromtxt(
                csv_path,
                delimiter=",",
                names=True,
                dtype=float,
                encoding="utf-8",
            )

        self.assertIn("is_settling", csv_data.dtype.names)
        self.assertEqual(1.0, csv_data["is_settling"][0])

    def test_calculator_writes_velocity_and_mu_columns_to_csv(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 1.0, 2.0]),
            "trajectory_x_mm": np.array([0.0, 3.0, 6.0]),
            "trajectory_y_mm": np.array([0.0, 4.0, 4.0]),
            "cumulative_mu": np.array([1.0, 3.0, 6.0]),
        }
        log_data = {
            "time_ms": np.array([0.0, 1000.0, 2000.0]),
            "x": np.array([0.0, 3.0, 6.0]),
            "y": np.array([0.0, 4.0, 4.0]),
            "x_raw": np.array([10.0, 11.0, 12.0]),
            "y_raw": np.array([20.0, 21.0, 22.0]),
            "layer_num": np.array([2.0, 2.0, 2.0]),
            "beam_on_off": np.array([50000.0, 50000.0, 50000.0]),
            "mu": np.array([0.5, 2.5, 5.0]),
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "debug.csv")
            calculate_differences_for_layer(
                plan_layer,
                log_data,
                save_to_csv=True,
                csv_filename=csv_path,
            )

            csv_data = np.genfromtxt(
                csv_path,
                delimiter=",",
                names=True,
                dtype=float,
                encoding="utf-8",
            )

        self.assertIn("log_velocity_mm_s", csv_data.dtype.names)
        self.assertIn("interp_plan_mu", csv_data.dtype.names)
        self.assertIn("log_mu", csv_data.dtype.names)
        np.testing.assert_allclose(csv_data["log_velocity_mm_s"], [0.0, 5.0, 3.0])
        np.testing.assert_allclose(csv_data["interp_plan_mu"], [1.0, 3.0, 6.0])
        np.testing.assert_allclose(csv_data["log_mu"], [0.5, 2.5, 5.0])

    def test_calculator_excludes_boundary_carryover_after_transit_from_filtered_stats(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 1.0, 2.0, 3.0]),
            "trajectory_x_mm": np.array([0.0, 20.0, 20.0, 30.0]),
            "trajectory_y_mm": np.array([0.0, 0.0, 0.0, 0.0]),
            "cumulative_mu": np.array([0.01, 0.010452, 0.044452, 0.094452]),
            "mu": np.array([0.01, 0.000452, 0.034, 0.05]),
            "spot_is_transit_min_dose": np.array([False, True, False, False]),
            "spot_scan_speed_mm_s": np.array([0.0, 20000.0, 200.0, 1000.0]),
        }
        log_data = {
            "time_ms": np.array([0.0, 200.0, 800.0, 1000.0, 1000.4, 1001.0, 1002.0, 2000.0, 3000.0]),
            "x": np.array([0.0, 4.0, 16.0, 35.0, 30.0, 24.0, 20.0, 20.0, 30.0]),
            "y": np.zeros(9),
        }
        config = {
            "SETTLING_THRESHOLD_MM": 100.0,
            "SETTLING_CONSECUTIVE_SAMPLES": 1,
            "ZERO_DOSE_FILTER_ENABLED": True,
            "ZERO_DOSE_BOUNDARY_HOLDOFF_S": 0.001,
        }

        results = calculate_differences_for_layer(plan_layer, log_data, config=config)

        np.testing.assert_array_equal(
            results["assigned_spot_index"],
            np.array([0, 1, 1, 1, 2, 2, 2, 2, 3]),
        )
        np.testing.assert_array_equal(
            results["sample_is_transit_min_dose"],
            np.array([False, True, True, True, False, False, False, False, False]),
        )
        np.testing.assert_array_equal(
            results["sample_is_boundary_carryover"],
            np.array([False, False, False, False, True, True, False, False, False]),
        )
        np.testing.assert_array_equal(
            results["sample_is_included_filtered_stats"],
            np.array([True, False, False, False, False, False, True, True, True]),
        )
        self.assertAlmostEqual(results["max_abs_diff_x"], 15.0)
        self.assertAlmostEqual(results["filtered_max_abs_diff_x"], 0.0)

    def test_calculator_falls_back_to_raw_when_filtered_mask_is_empty(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 1.0]),
            "trajectory_x_mm": np.array([0.0, 10.0]),
            "trajectory_y_mm": np.array([0.0, 0.0]),
            "mu": np.array([0.0, 0.000452]),
            "spot_is_transit_min_dose": np.array([True, True]),
            "spot_scan_speed_mm_s": np.array([20000.0, 20000.0]),
        }
        log_data = {
            "time_ms": np.array([0.0, 1000.0]),
            "x": np.array([0.0, 8.0]),
            "y": np.array([0.0, 0.0]),
        }
        config = {
            "SETTLING_THRESHOLD_MM": 100.0,
            "SETTLING_CONSECUTIVE_SAMPLES": 1,
            "ZERO_DOSE_FILTER_ENABLED": True,
        }

        results = calculate_differences_for_layer(plan_layer, log_data, config=config)

        self.assertTrue(results["filtered_stats_fallback_to_raw"])
        self.assertAlmostEqual(results["filtered_max_abs_diff_x"], results["max_abs_diff_x"])

if __name__ == '__main__':
    unittest.main()
