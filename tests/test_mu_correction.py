import unittest
import numpy as np

from src.mu_correction import apply_mu_correction, get_monitor_range_factor


class TestMuCorrection(unittest.TestCase):
    def test_monitor_range_code_1_uses_spec_ratio_relative_to_code_2(self):
        self.assertAlmostEqual(get_monitor_range_factor(1), 160.0 / 470.0)

    def test_apply_mu_correction_exposes_corrected_per_sample_weights(self):
        log_data = {
            "dose1_au": np.array([1.0, 2.0, 3.0], dtype=np.float32),
            "mu": np.array([1.0, 3.0, 6.0], dtype=np.float32),
        }

        corrected = apply_mu_correction(
            log_data,
            nominal_energy=150.0,
            monitor_range_code=2,
        )

        self.assertIn("mu_per_sample_corrected", corrected)
        np.testing.assert_allclose(
            corrected["mu"],
            np.cumsum(corrected["mu_per_sample_corrected"]),
        )


if __name__ == "__main__":
    unittest.main()
