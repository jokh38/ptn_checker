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

if __name__ == '__main__':
    unittest.main()
