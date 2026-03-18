import os
import sys

# Add the project root to the Python path for all tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set matplotlib backend to non-interactive for headless testing
import matplotlib
matplotlib.use('Agg')

import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ImplicitVRLittleEndian


def create_dummy_dcm_file(filepath, machine_name="TestMachine"):
    """Creates a dummy DICOM RTPLAN file for testing.

    Shared helper used by test_main.py, test_calculator.py, and test_dicom_parser.py.

    Args:
        filepath: Path where the DICOM file will be written.
        machine_name: Treatment machine name to embed in the file.
    """
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = pydicom.uid.UID('1.2.840.10008.5.1.4.1.1.481.5')
    file_meta.MediaStorageSOPInstanceUID = pydicom.uid.UID("1.2.3")
    file_meta.ImplementationClassUID = pydicom.uid.UID("1.2.3.4")
    file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

    ds = Dataset()
    ds.PatientName = "Test^Patient"
    ds.PatientID = "123456"

    ion_beam_sequence = Dataset()
    ion_beam_sequence.TreatmentMachineName = machine_name
    ion_beam_sequence.BeamNumber = 1

    # Create first control point
    cp1 = Dataset()
    cp1.ControlPointIndex = '0'
    cp1.GantryAngle = 0
    cp1.CumulativeMetersetWeight = 0.0
    bld_sequence1 = Dataset()
    bld_sequence1.RTBeamLimitingDeviceType = 'MLCX'
    bld_sequence1.LeafJawPositions = [str(i) for i in range(120)]
    cp1.BeamLimitingDevicePositionSequence = [bld_sequence1]
    cp1.add_new((0x300b, 0x1094), 'OB', b'\x00' * 8 * 10)  # 10 spots
    cp1.add_new((0x300b, 0x1096), 'OB', b'\x00' * 4 * 10)

    # Create second control point
    cp2 = Dataset()
    cp2.ControlPointIndex = '1'
    cp2.GantryAngle = 0
    cp2.CumulativeMetersetWeight = 10.0
    bld_sequence2 = Dataset()
    bld_sequence2.RTBeamLimitingDeviceType = 'MLCX'
    bld_sequence2.LeafJawPositions = [str(i) for i in range(120)]
    cp2.BeamLimitingDevicePositionSequence = [bld_sequence2]
    cp2.add_new((0x300b, 0x1094), 'OB', b'\x00' * 8 * 10)
    cp2.add_new((0x300b, 0x1096), 'OB', b'\x00' * 4 * 10)

    ion_beam_sequence.IonControlPointSequence = [cp1, cp2]
    ds.IonBeamSequence = [ion_beam_sequence]

    ds.file_meta = file_meta
    ds.is_little_endian = True
    ds.is_implicit_VR = True
    ds.save_as(filepath, write_like_original=False)
