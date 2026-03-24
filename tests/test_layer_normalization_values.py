import csv
import os
import tempfile
import unittest
from unittest import mock

import numpy as np

from src import layer_normalization_values


class TestLayerNormalizationValues(unittest.TestCase):
    def test_run_analysis_writes_layer_and_summary_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = os.path.join(temp_dir, "logs")
            output_dir = os.path.join(temp_dir, "out")
            os.makedirs(log_dir)
            os.makedirs(output_dir)

            dcm_file = os.path.join(temp_dir, "plan.dcm")
            with open(dcm_file, "wb") as f:
                f.write(b"")

            ptn_paths = []
            for name in ("001.ptn", "002.ptn"):
                path = os.path.join(log_dir, name)
                with open(path, "wb") as f:
                    f.write(b"ptn")
                ptn_paths.append(path)

            plan_data = {
                "machine_name": "G1",
                "beams": {
                    "2": {
                        "name": "BeamA",
                        "layers": {
                            0: {"mu": np.array([2.0, 3.0])},
                            2: {"mu": np.array([1.5, 2.5])},
                        },
                    }
                },
            }
            parsed_logs = [
                {"mu": np.array([2.0, 5.0]), "dose1_au": np.array([1.0, 1.0])},
                {"mu": np.array([1.0, 2.0]), "dose1_au": np.array([1.0, 1.0])},
            ]

            with mock.patch.object(
                layer_normalization_values, "load_plan_and_machine_config", return_value=(plan_data, {})
            ), mock.patch.object(
                layer_normalization_values,
                "parse_planrange_for_directory",
                return_value={
                    os.path.abspath(ptn_paths[0]): mock.Mock(
                        energy=150.0,
                        dose1_range_code=2,
                        dose2_range_code=3,
                        plan_dose1_range_code=4,
                        plan_dose2_range_code=3,
                    ),
                    os.path.abspath(ptn_paths[1]): mock.Mock(
                        energy=150.0,
                        dose1_range_code=2,
                        dose2_range_code=2,
                        plan_dose1_range_code=2,
                        plan_dose2_range_code=2,
                    ),
                },
            ), mock.patch.object(
                layer_normalization_values,
                "parse_ptn_with_optional_mu_correction",
                side_effect=parsed_logs,
            ):
                layer_csv, summary_csv = layer_normalization_values.run_analysis(
                    log_dir=log_dir,
                    dcm_file=dcm_file,
                    output_dir=output_dir,
                )

            self.assertTrue(os.path.exists(layer_csv))
            self.assertTrue(os.path.exists(summary_csv))

            with open(layer_csv, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(2, len(rows))
            self.assertEqual("BeamA", rows[0]["beam_name"])
            self.assertAlmostEqual(1.0, float(rows[0]["normalization_ratio"]))
            self.assertAlmostEqual(2.0, float(rows[1]["normalization_ratio"]))
            self.assertEqual("2", rows[0]["DOSE1_RANGE"])
            self.assertEqual(
                "PLAN_DOSE1_RANGE(4) != DOSE1_RANGE(2)",
                rows[0]["RANGE_PLAN_LOG_DIFF"],
            )
            self.assertEqual(
                "DOSE1_RANGE(2) != DOSE2_RANGE(3)",
                rows[0]["RANGE_1_2_DIFF"],
            )
            self.assertEqual("2", rows[1]["DOSE1_RANGE"])
            self.assertEqual("", rows[1]["RANGE_PLAN_LOG_DIFF"])
            self.assertEqual("", rows[1]["RANGE_1_2_DIFF"])

            with open(summary_csv, newline="", encoding="utf-8") as f:
                summary_rows = list(csv.DictReader(f))
            self.assertEqual(2, len(summary_rows))
            self.assertEqual("beam", summary_rows[0]["scope"])
            self.assertEqual("machine", summary_rows[1]["scope"])
            self.assertAlmostEqual(9.0 / 7.0, float(summary_rows[0]["total_ratio"]))
            self.assertAlmostEqual(1.5, float(summary_rows[1]["layer_ratio_mean"]))


if __name__ == "__main__":
    unittest.main()
