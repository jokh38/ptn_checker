import unittest
import os
import tempfile
import shutil

# Add src to path to allow for imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config_loader import parse_scv_init

class TestConfigLoader(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_file_path = os.path.join(self.test_dir, "scv_init_G1.txt")
        with open(self.config_file_path, 'w') as f:
            f.write("XPOSGAIN\t1.23\n")
            f.write("YPOSGAIN\t4.56\n")
            f.write("XPOSOFFSET\t-10\n")
            f.write("YPOSOFFSET\t20\n")
            f.write("TIMEGAIN\t0.001\n")
            f.write("# This is a comment\n")
            f.write("SOME_OTHER_PARAM\tVALUE\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_parse_scv_init(self):
        """
        Test that the scv_init file is parsed correctly.
        """
        config = parse_scv_init(self.config_file_path)

        self.assertIn('XPOSGAIN', config)
        self.assertEqual(config['XPOSGAIN'], 1.23)

        self.assertIn('YPOSGAIN', config)
        self.assertEqual(config['YPOSGAIN'], 4.56)

        self.assertIn('XPOSOFFSET', config)
        self.assertEqual(config['XPOSOFFSET'], -10.0)

        self.assertIn('YPOSOFFSET', config)
        self.assertEqual(config['YPOSOFFSET'], 20.0)

        self.assertIn('TIMEGAIN', config)
        self.assertEqual(config['TIMEGAIN'], 0.001)

        self.assertNotIn('SOME_OTHER_PARAM', config) # Should only parse specific keys
        self.assertNotIn('# This is a comment', config)


if __name__ == '__main__':
    unittest.main()