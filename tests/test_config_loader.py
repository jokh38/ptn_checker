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
            f.write('  report_style: "classic"\n')
            f.write('  save_debug_csv: "on"\n')

        config = parse_yaml_config(yaml_path)

        self.assertEqual(config["REPORT_STYLE"], "classic")
        self.assertEqual(config["SAVE_DEBUG_CSV"], "on")

    def test_parse_yaml_config_rejects_invalid_report_style(self):
        yaml_path = os.path.join(self.test_dir, "config.yaml")
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write("# PTN Checker Configuration\n")
            f.write("app:\n")
            f.write('  report_style: "invalid"\n')
            f.write('  save_debug_csv: "off"\n')

        with self.assertRaisesRegex(ValueError, "REPORT_STYLE"):
            parse_yaml_config(yaml_path)


if __name__ == "__main__":
    unittest.main()
