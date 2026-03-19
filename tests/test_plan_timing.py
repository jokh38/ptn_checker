import unittest

import numpy as np

from src.plan_timing import (
    build_layer_time_trajectory,
    get_doserate_for_energy,
    load_doserate_table,
)


class TestPlanTiming(unittest.TestCase):
    def test_load_doserate_table_parses_matlab_format(self):
        table = load_doserate_table()
        self.assertEqual(table.shape[1], 2)
        self.assertGreater(table.shape[0], 0)
        self.assertEqual(table[0, 0], 230.0)

    def test_get_doserate_for_energy_returns_table_value(self):
        value = get_doserate_for_energy(150.0)
        self.assertGreater(value, 0)

    def test_get_doserate_for_energy_returns_zero_for_missing(self):
        value = get_doserate_for_energy(9999.0)
        self.assertEqual(value, 0)

    def test_build_layer_time_trajectory_continuous_motion(self):
        positions_cm = np.array(
            [
                [0.0, 0.0],
                [10.0, 0.0],
                [10.0, 20.0],
            ]
        )
        mu = np.array([1.0, 2.0, 0.0])
        trajectory = build_layer_time_trajectory(
            positions_cm=positions_cm,
            mu=mu,
            energy=150.0,
        )
        self.assertEqual(trajectory["time_axis_s"][0], 0.0)
        self.assertEqual(len(trajectory["time_axis_s"]), 3)
        self.assertGreaterEqual(trajectory["layer_doserate_mu_per_s"], 1.4)
        self.assertEqual(len(trajectory["time_axis_s"]), len(trajectory["x_cm"]))
        self.assertEqual(len(trajectory["time_axis_s"]), len(trajectory["y_cm"]))
        self.assertGreater(trajectory["total_time_s"], 0.0)
        np.testing.assert_array_equal(trajectory["x_cm"], positions_cm[:, 0])
        np.testing.assert_array_equal(trajectory["y_cm"], positions_cm[:, 1])

    def test_zero_mu_segment_uses_max_speed_transit_time(self):
        positions_cm = np.array(
            [
                [0.0, 0.0],
                [20.0, 0.0],
            ]
        )
        mu = np.array([0.0, 0.0])
        trajectory = build_layer_time_trajectory(
            positions_cm=positions_cm,
            mu=mu,
            energy=150.0,
        )
        self.assertTrue(np.isclose(trajectory["total_time_s"], 20.0 / 2000.0))


if __name__ == "__main__":
    unittest.main()
