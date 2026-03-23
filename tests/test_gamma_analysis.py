import unittest

import numpy as np

from src.gamma_analysis import perform_fluence_gamma


class TestGammaAnalysis(unittest.TestCase):
    def test_identical_fluence_maps_have_near_perfect_pass_rate(self):
        grid_x, grid_y = np.meshgrid(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
        plan_grid = np.array([[1.0, 0.5], [0.2, 0.1]])
        log_grid = plan_grid.copy()
        config = {
            "fluence_percent_threshold": 3.0,
            "distance_mm_threshold": 2.0,
            "lower_percent_fluence_cutoff": 10.0,
        }

        results = perform_fluence_gamma(plan_grid, log_grid, grid_x, grid_y, config)

        self.assertGreaterEqual(results["pass_rate"], 0.99)
        self.assertAlmostEqual(results["gamma_mean"], 0.0, places=6)
        self.assertAlmostEqual(results["gamma_max"], 0.0, places=6)

    def test_perturbed_fluence_map_lowers_pass_rate(self):
        grid_x, grid_y = np.meshgrid(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
        plan_grid = np.array([[1.0, 0.5], [0.2, 0.1]])
        log_grid = np.array([[0.2, 0.1], [0.05, 0.0]])
        config = {
            "fluence_percent_threshold": 3.0,
            "distance_mm_threshold": 2.0,
            "lower_percent_fluence_cutoff": 10.0,
        }

        results = perform_fluence_gamma(plan_grid, log_grid, grid_x, grid_y, config)

        self.assertLess(results["pass_rate"], 1.0)
        self.assertGreater(results["gamma_max"], 0.0)


if __name__ == "__main__":
    unittest.main()
