import unittest

from src.mu_correction import get_monitor_range_factor


class TestMuCorrection(unittest.TestCase):
    def test_monitor_range_code_1_uses_spec_ratio_relative_to_code_2(self):
        self.assertAlmostEqual(get_monitor_range_factor(1), 160.0 / 470.0)


if __name__ == "__main__":
    unittest.main()
