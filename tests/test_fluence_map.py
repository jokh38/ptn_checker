import unittest

import numpy as np

from src.fluence_map import (
    assign_log_samples_to_plan_spots,
    build_plan_fluence_points,
    rasterize_fluence_points,
)


class TestFluenceMap(unittest.TestCase):
    def test_build_plan_fluence_points_excludes_transit_min_dose_spots_by_default(self):
        plan_layer = {
            "positions": np.array([[0.0, 0.0], [5.0, 5.0], [10.0, 10.0]]),
            "mu": np.array([1.0, 2.0, 3.0]),
            "spot_is_transit_min_dose": np.array([False, True, False]),
        }

        points_xy, weights = build_plan_fluence_points(plan_layer)

        np.testing.assert_array_equal(points_xy, np.array([[0.0, 0.0], [10.0, 10.0]]))
        np.testing.assert_array_equal(weights, np.array([1.0, 3.0]))

    def test_assign_log_samples_to_plan_spots_tracks_unmatched_weight(self):
        plan_xy = np.array([[0.0, 0.0], [10.0, 10.0]])
        log_xy = np.array([[0.2, -0.1], [9.9, 10.1], [20.0, 20.0]])
        sample_weights = np.array([1.5, 2.5, 4.0])

        spot_weights, unmatched_weight, matched_mask = assign_log_samples_to_plan_spots(
            plan_xy,
            log_xy,
            sample_weights,
            spot_tolerance_mm=1.0,
        )

        np.testing.assert_array_equal(spot_weights, np.array([1.5, 2.5]))
        self.assertAlmostEqual(unmatched_weight, 4.0)
        np.testing.assert_array_equal(matched_mask, np.array([True, True, False]))

    def test_rasterize_fluence_points_preserves_total_fluence_with_smoothing(self):
        points_xy = np.array([[0.0, 0.0], [6.0, 0.0]])
        weights = np.array([2.0, 3.0])

        grid_x, grid_y, grid = rasterize_fluence_points(
            points_xy,
            weights,
            grid_resolution_mm=3.0,
            gaussian_sigma_mm=3.0,
        )

        self.assertGreater(grid_x.size, 0)
        self.assertGreater(grid_y.size, 0)
        self.assertAlmostEqual(float(np.sum(grid)), 5.0, places=6)


if __name__ == "__main__":
    unittest.main()
