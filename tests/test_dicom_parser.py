import unittest
import os
import numpy as np
import tempfile
import shutil
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ImplicitVRLittleEndian

from tests.conftest import create_dummy_dcm_file
from src.dicom_parser import (
    parse_dcm_file,
    F_SHI_spotW,
    F_SHI_spotP,
    _classify_transit_min_dose_spots,
)


class TestDicomParser(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.dcm_file_path = os.path.join(self.test_dir, "test.dcm")
        create_dummy_dcm_file(self.dcm_file_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_parse_dcm_file_smoke(self):
        """
        A simple smoke test to see if the function runs without crashing.
        """
        self.assertTrue(os.path.exists(self.dcm_file_path), "Test file does not exist")
        data = parse_dcm_file(self.dcm_file_path)
        self.assertIsInstance(data, dict)

    def test_parse_dcm_file_structure(self):
        """
        Test that the parsed data dictionary has the expected structure.
        """
        data = parse_dcm_file(self.dcm_file_path)
        self.assertIn("beams", data)
        self.assertIsInstance(data["beams"], dict)
        self.assertIn("machine_name", data)
        self.assertEqual(data['machine_name'], "TestMachine")

        self.assertIn(1, data["beams"])
        beam_data = data["beams"][1]

        self.assertIn("layers", beam_data)
        self.assertIsInstance(beam_data["layers"], dict)

        self.assertIn(0, beam_data["layers"])
        layer_data = beam_data["layers"][0]

        self.assertIn("positions", layer_data)
        self.assertIn("mu", layer_data)
        self.assertIn("cumulative_mu", layer_data)
        self.assertIn("energy", layer_data)
        self.assertIn("time_axis_s", layer_data)
        self.assertIn("trajectory_x_mm", layer_data)
        self.assertIn("trajectory_y_mm", layer_data)
        self.assertIn("layer_doserate_mu_per_s", layer_data)
        self.assertIn("total_time_s", layer_data)

        self.assertIsInstance(layer_data["positions"], np.ndarray)
        self.assertIsInstance(layer_data["mu"], np.ndarray)
        self.assertIsInstance(layer_data["cumulative_mu"], np.ndarray)
        self.assertIsInstance(layer_data["time_axis_s"], np.ndarray)
        self.assertIsInstance(layer_data["trajectory_x_mm"], np.ndarray)
        self.assertIsInstance(layer_data["trajectory_y_mm"], np.ndarray)

        self.assertEqual(layer_data["positions"].shape[1], 2)
        self.assertEqual(layer_data["positions"].shape[0], layer_data["mu"].shape[0])
        self.assertGreater(layer_data["total_time_s"], 0.0)
        self.assertEqual(len(layer_data["time_axis_s"]), len(layer_data["trajectory_x_mm"]))
        self.assertEqual(len(layer_data["time_axis_s"]), len(layer_data["trajectory_y_mm"]))

    def test_missing_ion_beam_sequence(self):
        """Test that parse_dcm_file raises AttributeError when IonBeamSequence is missing."""
        filepath = os.path.join(self.test_dir, "no_ion_beam.dcm")
        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = pydicom.uid.UID('1.2.840.10008.5.1.4.1.1.481.5')
        file_meta.MediaStorageSOPInstanceUID = pydicom.uid.UID("1.2.3")
        file_meta.ImplementationClassUID = pydicom.uid.UID("1.2.3.4")
        file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

        ds = Dataset()
        ds.PatientName = "Test^Patient"
        ds.PatientID = "123456"
        # Intentionally no IonBeamSequence
        ds.file_meta = file_meta
        ds.is_little_endian = True
        ds.is_implicit_VR = True
        ds.save_as(filepath, write_like_original=False)

        with self.assertRaises(AttributeError):
            parse_dcm_file(filepath)

    def test_F_SHI_spotW_known_values(self):
        """Test F_SHI_spotW with known input bytes and expected output."""
        # All zeros should produce a specific small value
        result = F_SHI_spotW(b'\x00\x00\x00\x00')
        self.assertIsInstance(result, float)
        # Zero exponent bytes: 2^(0//128) * 4^(-64+0) * (0.5 + 0) = 1 * 4^-64 * 0.5
        expected = 2**(0 // 128) * 4**(-64 + 0) * (0.5 + 0)
        self.assertAlmostEqual(result, expected, places=30)

    def test_F_SHI_spotP_known_values(self):
        """Test F_SHI_spotP with known input bytes and expected output."""
        # Test with zero bytes
        result = F_SHI_spotP(b'\x00\x00')
        self.assertIsInstance(result, float)

        # With bytes [0x80, 0x00]: x1=128, x2=0
        # sign=1, det_pos_x3=0, det_pos_x2=0, det_pos_x1=0
        # ind_helper=8-(2*1+1)+abs(1-1)=5, real_diff=0/32=0
        # x_real = 1*(4-0) = 4.0
        result2 = F_SHI_spotP(b'\x80\x00')
        self.assertAlmostEqual(result2, 4.0)

    def test_F_SHI_spotP_negative_position(self):
        """Test F_SHI_spotP produces negative values for high byte1."""
        # byte1 (x2) >= 128 means negative sign
        result = F_SHI_spotP(b'\x80\x80')
        self.assertLess(result, 0)

    def test_classify_transit_min_dose_spots_marks_high_speed_low_mu_runs(self):
        positions = np.array(
            [
                [0.0, 0.0],
                [20.0, 0.0],
                [40.0, 0.0],
                [40.1, 0.0],
            ]
        )
        mu = np.array([0.01, 0.000452, 0.000452, 0.05])
        segment_times_s = np.array([0.0, 0.001, 0.001, 0.01])

        transit, scan_speed = _classify_transit_min_dose_spots(
            positions_mm=positions,
            mu=mu,
            segment_times_s=segment_times_s,
        )

        np.testing.assert_array_equal(transit, np.array([False, True, True, False]))
        self.assertGreaterEqual(scan_speed[1], 10000.0)
        self.assertGreaterEqual(scan_speed[2], 10000.0)

    def test_classify_transit_min_dose_spots_keeps_isolated_low_mu_treatment(self):
        positions = np.array(
            [
                [0.0, 0.0],
                [0.2, 0.0],
                [0.4, 0.0],
            ]
        )
        mu = np.array([0.02, 0.0008, 0.03])
        segment_times_s = np.array([0.0, 0.01, 0.01])

        transit, _ = _classify_transit_min_dose_spots(
            positions_mm=positions,
            mu=mu,
            segment_times_s=segment_times_s,
        )

        np.testing.assert_array_equal(transit, np.array([False, False, False]))


if __name__ == '__main__':
    unittest.main()
