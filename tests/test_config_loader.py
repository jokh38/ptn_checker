import os
import shutil
import tempfile
import unittest

from src.config_loader import parse_yaml_config, parse_scv_init


class TestConfigLoader(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file_path = os.path.join(self.test_dir, "scv_init_G1.txt")
        with open(self.config_file_path, "w") as f:
            f.write("XPOSGAIN\t1.23\n")
            f.write("YPOSGAIN\t4.56\n")
            f.write("XPOSOFFSET\t-10\n")
            f.write("YPOSOFFSET\t20\n")
            f.write("TIMEGAIN\t0.001\n")
            f.write("SETTLING_THRESHOLD_MM\t0.5\n")
            f.write("SETTLING_WINDOW_SAMPLES\t10\n")
            f.write("SETTLING_CONSECUTIVE_SAMPLES\t3\n")
            f.write("# This is a comment\n")
            f.write("SOME_OTHER_PARAM\tVALUE\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_parse_scv_init(self):
        """
        Test that the scv_init file is parsed correctly.
        """
        config = parse_scv_init(self.config_file_path)

        self.assertIn("XPOSGAIN", config)
        self.assertEqual(config["XPOSGAIN"], 1.23)

        self.assertIn("YPOSGAIN", config)
        self.assertEqual(config["YPOSGAIN"], 4.56)

        self.assertIn("XPOSOFFSET", config)
        self.assertEqual(config["XPOSOFFSET"], -10.0)

        self.assertIn("YPOSOFFSET", config)
        self.assertEqual(config["YPOSOFFSET"], 20.0)

        self.assertIn("TIMEGAIN", config)
        self.assertEqual(config["TIMEGAIN"], 0.001)

        self.assertIn("SETTLING_THRESHOLD_MM", config)
        self.assertEqual(config["SETTLING_THRESHOLD_MM"], 0.5)

        self.assertIn("SETTLING_WINDOW_SAMPLES", config)
        self.assertEqual(config["SETTLING_WINDOW_SAMPLES"], 10.0)

        self.assertIn("SETTLING_CONSECUTIVE_SAMPLES", config)
        self.assertEqual(config["SETTLING_CONSECUTIVE_SAMPLES"], 3.0)

        self.assertNotIn("SOME_OTHER_PARAM", config)  # Should only parse specific keys
        self.assertNotIn("# This is a comment", config)

    def test_parse_yaml_config(self):
        yaml_path = os.path.join(self.test_dir, "config.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write("# PTN Checker Configuration\n")
            f.write("app:\n")
            f.write("  report_style_summary: false\n")
            f.write("  export_pdf_report: false\n")
            f.write("  export_report_csv: true\n")
            f.write("  save_debug_csv: true\n")
            f.write("  report_detail_pdf: false\n")
            f.write("zero_dose_filter:\n")
            f.write("  enabled: true\n")
            f.write("  max_mu: 0.002\n")
            f.write("  machine_min_mu: 0.000452\n")
            f.write("  min_scan_speed_mm_s: 12000\n")
            f.write("  min_run_length: 3\n")
            f.write("  keep_first_zero_mu_spot: false\n")
            f.write("  boundary_holdoff_s: 0.0008\n")
            f.write("  post_minimal_dose_boundary_s: 0.0012\n")
            f.write('  report_mode: "both"\n')

        config = parse_yaml_config(yaml_path)

        self.assertFalse(config["REPORT_STYLE_SUMMARY"])
        self.assertFalse(config["EXPORT_PDF_REPORT"])
        self.assertTrue(config["EXPORT_REPORT_CSV"])
        self.assertTrue(config["SAVE_DEBUG_CSV"])
        self.assertFalse(config["REPORT_DETAIL_PDF"])
        self.assertTrue(config["ZERO_DOSE_FILTER_ENABLED"])
        self.assertEqual(config["ZERO_DOSE_MAX_MU"], 0.002)
        self.assertEqual(config["ZERO_DOSE_MACHINE_MIN_MU"], 0.000452)
        self.assertEqual(config["ZERO_DOSE_MIN_SCAN_SPEED_MM_S"], 12000)
        self.assertEqual(config["ZERO_DOSE_MIN_RUN_LENGTH"], 3)
        self.assertFalse(config["ZERO_DOSE_KEEP_FIRST_ZERO_MU_SPOT"])
        self.assertEqual(config["ZERO_DOSE_BOUNDARY_HOLDOFF_S"], 0.0008)
        self.assertEqual(
            config["ZERO_DOSE_POST_MINIMAL_DOSE_BOUNDARY_S"],
            0.0012,
        )
        self.assertEqual(config["ZERO_DOSE_REPORT_MODE"], "both")

    def test_parse_yaml_config_maps_point_gamma_analysis_settings(self):
        yaml_path = os.path.join(self.test_dir, "config.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write("# PTN Checker Configuration\n")
            f.write("app:\n")
            f.write("  report_style_summary: true\n")
            f.write("  export_pdf_report: false\n")
            f.write("  export_report_csv: false\n")
            f.write("  save_debug_csv: false\n")
            f.write("  report_detail_pdf: false\n")
            f.write("  analysis_mode: point_gamma\n")
            f.write("point_gamma:\n")
            f.write("  fluence_percent_threshold: 5.0\n")
            f.write("  distance_mm_threshold: 2.0\n")
            f.write("  lower_percent_fluence_cutoff: 10.0\n")
            f.write("zero_dose_filter:\n")
            f.write("  enabled: false\n")
            f.write('  report_mode: "filtered"\n')

        config = parse_yaml_config(yaml_path)

        self.assertEqual(config["ANALYSIS_MODE"], "point_gamma")
        self.assertEqual(config["GAMMA_FLUENCE_PERCENT_THRESHOLD"], 5.0)
        self.assertEqual(config["GAMMA_DISTANCE_MM_THRESHOLD"], 2.0)
        self.assertNotIn("GAMMA_SPOT_TOLERANCE_MM", config)
        self.assertNotIn("GAMMA_REQUIRE_PLANRANGE_MU_CORRECTION", config)
        self.assertNotIn("GAMMA_ALLOW_RELATIVE_FLUENCE_FALLBACK", config)

    def test_parse_yaml_config_accepts_point_gamma_analysis_mode(self):
        yaml_path = os.path.join(self.test_dir, "config.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write("# PTN Checker Configuration\n")
            f.write("app:\n")
            f.write("  report_style_summary: true\n")
            f.write("  export_pdf_report: false\n")
            f.write("  export_report_csv: false\n")
            f.write("  save_debug_csv: false\n")
            f.write("  report_detail_pdf: false\n")
            f.write("  analysis_mode: point_gamma\n")
            f.write("point_gamma:\n")
            f.write("  fluence_percent_threshold: 5.0\n")
            f.write("  distance_mm_threshold: 2.0\n")
            f.write("  lower_percent_fluence_cutoff: 10.0\n")

        config = parse_yaml_config(yaml_path)

        self.assertEqual(config["ANALYSIS_MODE"], "point_gamma")

    def test_parse_yaml_config_maps_machine_specific_normalization_factors(self):
        yaml_path = os.path.join(self.test_dir, "config.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write("app:\n")
            f.write("  report_style_summary: true\n")
            f.write("  export_pdf_report: false\n")
            f.write("  export_report_csv: false\n")
            f.write("  save_debug_csv: false\n")
            f.write("  report_detail_pdf: false\n")
            f.write("  analysis_mode: point_gamma\n")
            f.write("point_gamma:\n")
            f.write("  fluence_percent_threshold: 5.0\n")
            f.write("  distance_mm_threshold: 2.0\n")
            f.write("  normalization_factor_by_machine:\n")
            f.write("    G1: 5.5e-7\n")
            f.write("    g2: 5.0e-7\n")

        config = parse_yaml_config(yaml_path)

        self.assertEqual(config["GAMMA_FLUENCE_PERCENT_THRESHOLD"], 5.0)
        self.assertEqual(config["GAMMA_DISTANCE_MM_THRESHOLD"], 2.0)
        self.assertEqual(
            config["GAMMA_NORMALIZATION_FACTOR_BY_MACHINE"],
            {"G1": 5.5e-7, "G2": 5.0e-7},
        )

    def test_parse_yaml_config_rejects_legacy_gamma_analysis_mode(self):
        yaml_path = os.path.join(self.test_dir, "config.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write("app:\n")
            f.write("  report_style_summary: true\n")
            f.write("  export_pdf_report: false\n")
            f.write("  export_report_csv: false\n")
            f.write("  save_debug_csv: false\n")
            f.write("  report_detail_pdf: false\n")
            f.write("  analysis_mode: gamma\n")

        with self.assertRaisesRegex(ValueError, "ANALYSIS_MODE"):
            parse_yaml_config(yaml_path)

    def test_parse_yaml_config_rejects_invalid_report_style(self):
        yaml_path = os.path.join(self.test_dir, "config.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write("# PTN Checker Configuration\n")
            f.write("app:\n")
            f.write('  report_style_summary: "invalid"\n')
            f.write("  export_pdf_report: true\n")
            f.write("  export_report_csv: false\n")
            f.write("  save_debug_csv: false\n")
            f.write("  report_detail_pdf: false\n")

        with self.assertRaisesRegex(ValueError, "REPORT_STYLE_SUMMARY"):
            parse_yaml_config(yaml_path)

    def test_parse_yaml_config_rejects_invalid_report_detail_pdf(self):
        yaml_path = os.path.join(self.test_dir, "config.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write("app:\n")
            f.write("  report_style_summary: true\n")
            f.write("  export_pdf_report: true\n")
            f.write("  export_report_csv: false\n")
            f.write("  save_debug_csv: false\n")
            f.write('  report_detail_pdf: "invalid"\n')

        with self.assertRaisesRegex(ValueError, "REPORT_DETAIL_PDF"):
            parse_yaml_config(yaml_path)

    def test_parse_yaml_config_rejects_invalid_zero_dose_report_mode(self):
        yaml_path = os.path.join(self.test_dir, "config.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write("app:\n")
            f.write("  report_style_summary: true\n")
            f.write("  export_pdf_report: true\n")
            f.write("  export_report_csv: false\n")
            f.write("  save_debug_csv: false\n")
            f.write("  report_detail_pdf: false\n")
            f.write("zero_dose_filter:\n")
            f.write('  report_mode: "invalid"\n')

        with self.assertRaisesRegex(ValueError, "ZERO_DOSE_REPORT_MODE"):
            parse_yaml_config(yaml_path)

    def test_parse_yaml_config_ignores_legacy_point_gamma_kernel_fields(self):
        yaml_path = os.path.join(self.test_dir, "config.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write("app:\n")
            f.write("  report_style_summary: true\n")
            f.write("  export_pdf_report: false\n")
            f.write("  export_report_csv: false\n")
            f.write("  save_debug_csv: false\n")
            f.write("  report_detail_pdf: false\n")
            f.write("  analysis_mode: point_gamma\n")
            f.write("point_gamma:\n")
            f.write("  fluence_percent_threshold: 5.0\n")
            f.write("  distance_mm_threshold: 2.0\n")
            f.write("  lower_percent_fluence_cutoff: 10.0\n")
            f.write("  grid_resolution_mm: 3.0\n")
            f.write("  spot_tolerance_mm: 1.0\n")
            f.write("  gaussian_sigma_mm: 3.0\n")

        config = parse_yaml_config(yaml_path)

        self.assertEqual(config["ANALYSIS_MODE"], "point_gamma")
        self.assertNotIn("GAMMA_GRID_RESOLUTION_MM", config)
        self.assertNotIn("GAMMA_SPOT_TOLERANCE_MM", config)
        self.assertNotIn("GAMMA_GAUSSIAN_SIGMA_MM", config)


if __name__ == "__main__":
    unittest.main()
