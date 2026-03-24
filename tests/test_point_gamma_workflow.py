import unittest

import numpy as np

from src.point_gamma_workflow import (
    _build_time_aligned_series,
    _normalize_log_counts,
    calculate_point_gamma_for_layer,
)


class TestPointGammaWorkflow(unittest.TestCase):
    def test_normalize_log_counts_applies_machine_factor(self):
        log_data = {"dose1_au": np.array([2.0, 4.0], dtype=float)}
        config = {"GAMMA_NORMALIZATION_FACTOR": 0.5}

        normalized = _normalize_log_counts(log_data, config)

        np.testing.assert_allclose(normalized, np.array([1.0, 2.0], dtype=float))

    def test_build_time_aligned_series_uses_fixed_60us_grid(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 0.00012, 0.00024], dtype=float),
            "trajectory_x_mm": np.array([0.0, 2.0, 4.0], dtype=float),
            "trajectory_y_mm": np.array([0.0, 0.0, 0.0], dtype=float),
            "cumulative_mu": np.array([0.0, 2.0, 4.0], dtype=float),
        }
        log_data = {
            "time_ms": np.array([0.0, 0.06, 0.12, 0.18, 0.24], dtype=float),
            "x_mm": np.array([0.0, 1.0, 2.0, 3.0, 4.0], dtype=float),
            "y_mm": np.zeros(5, dtype=float),
            "dose1_au": np.array([0.0, 1.0, 1.0, 1.0, 1.0], dtype=float),
        }
        config = {"GAMMA_NORMALIZATION_FACTOR": 1.0}

        aligned = _build_time_aligned_series(plan_layer, log_data, config)

        np.testing.assert_allclose(
            aligned["time_s"],
            np.array([0.0, 0.00006, 0.00012, 0.00018, 0.00024], dtype=float),
        )
        np.testing.assert_allclose(
            aligned["plan_count"],
            np.array([0.0, 1.0, 1.0, 1.0, 1.0], dtype=float),
        )
        np.testing.assert_allclose(
            aligned["log_count"],
            np.array([0.0, 1.0, 1.0, 1.0, 1.0], dtype=float),
        )

    def test_calculate_point_gamma_for_layer_returns_pass_fail_metrics(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 0.00012, 0.00024], dtype=float),
            "trajectory_x_mm": np.array([0.0, 2.0, 4.0], dtype=float),
            "trajectory_y_mm": np.array([0.0, 0.0, 0.0], dtype=float),
            "cumulative_mu": np.array([0.0, 2.0, 4.0], dtype=float),
        }
        log_data = {
            "time_ms": np.array([0.0, 0.06, 0.12, 0.18, 0.24], dtype=float),
            "x_mm": np.array([0.0, 1.0, 2.0, 3.0, 4.0], dtype=float),
            "y_mm": np.zeros(5, dtype=float),
            "dose1_au": np.array([0.0, 1.0, 1.0, 1.0, 1.0], dtype=float),
        }
        config = {
            "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
            "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
            "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            "GAMMA_NORMALIZATION_FACTOR": 1.0,
        }

        results = calculate_point_gamma_for_layer(plan_layer, log_data, config)

        self.assertEqual("point_gamma", results["normalization_mode"])
        self.assertAlmostEqual(results["pass_rate"], 1.0)
        self.assertAlmostEqual(results["gamma_max"], 0.0)
        self.assertGreater(results["evaluated_point_count"], 0)
        self.assertGreaterEqual(results["gamma_map"].shape[0], 2)
        self.assertGreaterEqual(results["gamma_map"].shape[1], 2)

    def test_calculate_point_gamma_for_layer_includes_position_difference_metrics(self):
        plan_layer = {
            "time_axis_s": np.array([0.0, 0.00012, 0.00024], dtype=float),
            "trajectory_x_mm": np.array([0.0, 1.0, 2.0], dtype=float),
            "trajectory_y_mm": np.array([0.0, 0.0, 0.0], dtype=float),
            "cumulative_mu": np.array([0.0, 1.0, 2.0], dtype=float),
        }
        log_data = {
            "time_ms": np.array([0.0, 0.06, 0.12, 0.18, 0.24], dtype=float),
            "x_mm": np.array([0.0, 1.0, 2.0, 2.5, 2.0], dtype=float),
            "y_mm": np.zeros(5, dtype=float),
            "dose1_au": np.array([0.0, 1.0, 1.0, 1.0, 1.0], dtype=float),
        }
        config = {
            "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
            "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
            "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            "GAMMA_NORMALIZATION_FACTOR": 1.0,
        }

        results = calculate_point_gamma_for_layer(plan_layer, log_data, config)

        for key in (
            "diff_x",
            "diff_y",
            "mean_diff_x",
            "mean_diff_y",
            "std_diff_x",
            "std_diff_y",
            "max_abs_diff_x",
            "max_abs_diff_y",
            "rmse_x",
            "rmse_y",
            "p95_abs_diff_x",
            "p95_abs_diff_y",
        ):
            self.assertIn(key, results)

        self.assertEqual(results["normalization_mode"], "point_gamma")
        self.assertGreater(results["diff_x"].size, 0)
        self.assertGreater(results["diff_y"].size, 0)


if __name__ == "__main__":
    unittest.main()
