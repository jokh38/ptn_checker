import unittest

import numpy as np

from src.gamma_workflow import calculate_gamma_for_layer


class TestGammaWorkflow(unittest.TestCase):
    def test_primary_gamma_mode_applies_configured_normalization_factor(self):
        plan_layer = {
            "positions": np.array([[0.0, 0.0]], dtype=float),
            "mu": np.array([1.0], dtype=float),
            "spot_is_transit_min_dose": np.array([False]),
        }
        log_data = {
            "x_mm": np.array([0.0], dtype=float),
            "y_mm": np.array([0.0], dtype=float),
            "mu_per_sample_corrected": np.array([2.0], dtype=float),
            "planrange_metadata": {
                "found": True,
                "applied": True,
                "energy": 150.0,
                "dose1_range_code": 2,
            },
        }
        config = {
            "GAMMA_FLUENCE_PERCENT_THRESHOLD": 3.0,
            "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
            "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            "GAMMA_GRID_RESOLUTION_MM": 3.0,
            "GAMMA_SPOT_TOLERANCE_MM": 1.0,
            "GAMMA_REQUIRE_PLANRANGE_MU_CORRECTION": True,
            "GAMMA_ALLOW_RELATIVE_FLUENCE_FALLBACK": False,
            "GAMMA_USE_GAUSSIAN_SPOT_MODEL": False,
            "GAMMA_GAUSSIAN_SIGMA_MM": 3.0,
            "GAMMA_MAP_MARGIN_MM": 0.0,
            "GAMMA_NORMALIZATION_FACTOR": 0.5,
        }

        results = calculate_gamma_for_layer(plan_layer, log_data, config)

        self.assertEqual("planrange_corrected", results["normalization_mode"])
        self.assertTrue(results["used_planrange_mu_correction"])
        self.assertAlmostEqual(results["pass_rate"], 1.0)
        self.assertAlmostEqual(results["gamma_max"], 0.0)


if __name__ == "__main__":
    unittest.main()
