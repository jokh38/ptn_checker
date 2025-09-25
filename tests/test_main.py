import unittest
import os
import sys
import tempfile
import shutil
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ImplicitVRLittleEndian

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import find_ptn_files, run_analysis

class TestMain(unittest.TestCase):
    def setUp(self):
        """Set up a temporary directory with nested subdirectories and files."""
        self.test_dir = tempfile.mkdtemp()
        self.sub_dir = os.path.join(self.test_dir, "subdir1")
        self.nested_sub_dir = os.path.join(self.sub_dir, "subdir2")
        os.makedirs(self.nested_sub_dir)

        self.ptn_files = [
            os.path.join(self.test_dir, "file1.ptn"),
            os.path.join(self.sub_dir, "file2.ptn"),
            os.path.join(self.nested_sub_dir, "file3.ptn")
        ]

        for ptn_file in self.ptn_files:
            with open(ptn_file, "w") as f:
                f.write("CS\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n11\n12\n13\n14\n15\n16\n17\n18\n19\n20\n21\n22\n23\n24\n25\n26\n27\n28\n29\n30\n31\n32\n33\n34\n35\n36\n37\n38\n39\n40\n41\n42\n43\n44\n45\n46\n47\n48\n49\n50\n51\n52\n53\n54\n55\n56\n57\n58\n59\n60\n")

        # Create a non-ptn file to ensure it's not picked up
        with open(os.path.join(self.test_dir, "not_a_ptn.txt"), "w") as f:
            f.write("some other data")

        # Create a dummy DICOM file
        self.dcm_file = os.path.join(self.test_dir, "test.dcm")
        self.create_dummy_dcm_file(self.dcm_file, "G1") # Machine G1

        # Create dummy config files in the root (or where main.py expects them)
        self.create_dummy_config_file("scv_init_G1.txt")


    def tearDown(self):
        """Remove the temporary directory and its contents."""
        shutil.rmtree(self.test_dir)
        # Clean up config file
        if os.path.exists("scv_init_G1.txt"):
            os.remove("scv_init_G1.txt")


    def create_dummy_config_file(self, filename):
        with open(filename, 'w') as f:
            f.write("XPOSGAIN\t1.0\n")
            f.write("YPOSGAIN\t1.0\n")
            f.write("XPOSOFFSET\t0.0\n")
            f.write("YPOSOFFSET\t0.0\n")


    def create_dummy_dcm_file(self, filepath, machine_name="TestMachine"):
        """Creates a dummy DICOM file for testing."""
        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.481.5'
        file_meta.MediaStorageSOPInstanceUID = "1.2.3"
        file_meta.ImplementationClassUID = "1.2.3.4"
        file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

        ds = Dataset()
        ds.PatientName = "Test^Patient"
        ds.PatientID = "123456"

        ion_beam_sequence = Dataset()
        ion_beam_sequence.TreatmentMachineName = machine_name
        ion_beam_sequence.BeamNumber = 1

        # Create two control points for a layer
        cp1 = Dataset()
        cp1.ControlPointIndex = '0'
        cp1.CumulativeMetersetWeight = 0.0
        cp1.add_new((0x300b, 0x1094), 'OB', b'\x00' * 8 * 10) # 10 spots
        cp1.add_new((0x300b, 0x1096), 'OB', b'\x00' * 4 * 10)

        cp2 = Dataset()
        cp2.ControlPointIndex = '1'
        cp2.CumulativeMetersetWeight = 10.0

        ion_beam_sequence.IonControlPointSequence = [cp1, cp2]
        ds.IonBeamSequence = [ion_beam_sequence]

        ds.file_meta = file_meta
        ds.is_little_endian = True
        ds.is_implicit_VR = True
        ds.save_as(filepath, write_like_original=False)


    def test_find_ptn_files(self):
        """
        Test that find_ptn_files correctly finds all .ptn files recursively.
        """
        found_files = find_ptn_files(self.test_dir)
        self.assertEqual(len(self.ptn_files), len(found_files))
        self.assertCountEqual(self.ptn_files, found_files)

    def test_run_analysis_dcm_not_found(self):
        """
        Test that run_analysis raises FileNotFoundError for a missing DICOM file.
        """
        with self.assertRaisesRegex(FileNotFoundError, "DICOM file not found"):
            run_analysis(self.test_dir, "non_existent.dcm", "report.pdf")

    def test_run_analysis_no_ptn_files_found(self):
        """
        Test that run_analysis raises FileNotFoundError when no .ptn files are found.
        """
        empty_dir = os.path.join(self.test_dir, "empty_dir")
        os.makedirs(empty_dir)
        with self.assertRaisesRegex(FileNotFoundError, "No .ptn files found"):
            run_analysis(empty_dir, self.dcm_file, "report.pdf")

if __name__ == '__main__':
    unittest.main()
