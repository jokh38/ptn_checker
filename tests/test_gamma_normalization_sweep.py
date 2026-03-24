import unittest
from unittest import mock


from tools.gamma_normalization_sweep import (
    generate_linear_micro_factors,
    run_sweep,
    select_optimal_factor,
    summarize_factor_result,
)


class TestGammaNormalizationSweep(unittest.TestCase):
    def test_generate_linear_micro_factors_builds_expected_sequence(self):
        factors = generate_linear_micro_factors(start=1e-6, step=1e-6, count=5)

        self.assertEqual([1e-6, 2e-6, 3e-6, 4e-6, 5e-6], factors)

    def test_select_optimal_factor_uses_lowest_average_gamma_mean(self):
        factor_rows = [
            {
                "factor": 1e-6,
                "layer_gamma_means": [3.0, 4.0],
                "layer_pass_rates": [0.1, 0.2],
            },
            {
                "factor": 2e-6,
                "layer_gamma_means": [2.0, 2.5],
                "layer_pass_rates": [0.1, 0.1],
            },
            {
                "factor": 3e-6,
                "layer_gamma_means": [5.0, 6.0],
                "layer_pass_rates": [0.5, 0.5],
            },
        ]

        best = select_optimal_factor(factor_rows)

        self.assertEqual(2e-6, best["factor"])

    def test_summarize_factor_result_ignores_error_rows(self):
        summary = summarize_factor_result(
            1e-6,
            [
                {"gamma_mean": 2.0, "pass_rate": 0.2},
                {"status": "error"},
                {"gamma_mean": 4.0, "pass_rate": 0.4},
            ],
        )

        self.assertEqual(1e-6, summary["factor"])
        self.assertEqual(2, summary["layer_count"])
        self.assertAlmostEqual(3.0, summary["avg_gamma_mean"])
        self.assertAlmostEqual(0.3, summary["avg_pass_rate"])

    def test_run_sweep_uses_gamma_workflow_function_for_each_factor_and_layer(self):
        layer_pairs = [
            {
                "beam_number": 1,
                "beam_name": "Beam 1",
                "layer_index": 0,
                "layer_number": 1,
                "ptn_file": "001.ptn",
                "plan_layer": {"id": "plan"},
                "log_data": {"id": "log"},
                "analysis_config": {"base": "cfg"},
            }
        ]

        with mock.patch(
            "tools.gamma_normalization_sweep._collect_layer_pairs",
            return_value=layer_pairs,
        ), mock.patch(
            "tools.gamma_normalization_sweep.calculate_gamma_for_layer",
            side_effect=[
                {"gamma_mean": 2.0, "pass_rate": 0.25},
                {"gamma_mean": 1.0, "pass_rate": 0.5},
            ],
            create=True,
        ) as gamma_mock:
            result = run_sweep(
                "/tmp/logs",
                "/tmp/plan.dcm",
                start=1e-6,
                step=1e-6,
                count=2,
                app_config_path="config.yaml",
            )

        self.assertEqual(2, gamma_mock.call_count)
        self.assertEqual(2e-6, result["best"]["factor"])
        self.assertAlmostEqual(1.0, result["best"]["avg_gamma_mean"])
        self.assertAlmostEqual(0.5, result["best"]["avg_pass_rate"])


if __name__ == "__main__":
    unittest.main()
