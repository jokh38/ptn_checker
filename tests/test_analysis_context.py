import os
import shutil
import tempfile
import unittest
from unittest import mock

import numpy as np

from src.analysis_context import parse_ptn_with_optional_mu_correction


class TestAnalysisContext(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ptn_file = os.path.join(self.test_dir, "sample.ptn")
        dummy_ptn_data = np.arange(80, dtype=">u2")
        for i in range(10):
            dummy_ptn_data[i * 8 + 7] = 50000
        dummy_ptn_data.tofile(self.ptn_file)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_parse_ptn_with_optional_mu_correction_exposes_planrange_metadata(self):
        fake_log_data = {
            "time_ms": np.array([0.0], dtype=np.float32),
            "dose1_au": np.array([1.0], dtype=np.float32),
            "mu": np.array([1.0], dtype=np.float32),
            "x": np.array([0.0], dtype=np.float32),
            "y": np.array([0.0], dtype=np.float32),
        }
        planrange_lookup = {
            os.path.abspath(self.ptn_file): mock.Mock(
                energy=150.0,
                dose1_range_code=2,
            )
        }

        with mock.patch("src.analysis_context.parse_ptn_file", return_value=fake_log_data), mock.patch(
            "src.analysis_context.apply_mu_correction",
            side_effect=lambda log_data, nominal_energy, monitor_range_code: log_data,
        ):
            result = parse_ptn_with_optional_mu_correction(
                self.ptn_file,
                config={},
                planrange_lookup=planrange_lookup,
            )

        self.assertIn("planrange_metadata", result)
        self.assertTrue(result["planrange_metadata"]["found"])
        self.assertTrue(result["planrange_metadata"]["applied"])
        self.assertEqual(result["planrange_metadata"]["energy"], 150.0)
        self.assertEqual(result["planrange_metadata"]["dose1_range_code"], 2)


if __name__ == "__main__":
    unittest.main()
