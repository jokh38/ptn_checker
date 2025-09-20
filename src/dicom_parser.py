import pydicom
import numpy as np
import os


def parse_dcm_file(file_path: str) -> dict:
    """
    Parses a DICOM RTPLAN file to extract spot positions and MUs.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        plan = pydicom.dcmread(file_path)
    except pydicom.errors.InvalidDicomError:
        raise pydicom.errors.InvalidDicomError(f"Invalid DICOM file: {file_path}")

    plan_data = {'beams': {}}
    for i, beam in enumerate(plan.IonBeamSequence):
        try:
            beam_description = getattr(beam, 'BeamDescription', '')
            beam_name = getattr(beam, 'BeamName', '')
            if beam_description == "Site Setup" or beam_name == "SETUP":
                continue

            beam_data = {'layers': {}}
            ion_control_points = beam.IonControlPointSequence
            for i in range(0, len(ion_control_points), 2):
                cp_start = ion_control_points[i]
                if (i + 1) >= len(ion_control_points):
                    continue
                cp_end = ion_control_points[i+1]
                layer_index = cp_start.ControlPointIndex

                if (0x300b, 0x1094) not in cp_start or (0x300b, 0x1096) not in cp_start:
                    continue

                pos_map_bytes = cp_start[0x300b, 0x1094].value
                mu_map_bytes = cp_start[0x300b, 0x1096].value

                # Use np.frombuffer to directly parse the byte data
                positions_raw = np.frombuffer(pos_map_bytes, dtype=np.float32)
                positions = positions_raw.reshape(-1, 2)

                weights = np.frombuffer(mu_map_bytes, dtype=np.float32)

                total_mu_for_layer = (cp_end.CumulativeMetersetWeight -
                                      cp_start.CumulativeMetersetWeight)
                total_weight = np.sum(weights)

                if total_weight > 0:
                    mus = (weights / total_weight) * total_mu_for_layer
                else:
                    mus = np.zeros_like(weights, dtype=np.float32)

                beam_data['layers'][layer_index] = {
                    'positions': positions,
                    'mu': mus.astype(np.float32), # Ensure mu is also float32
                    'cumulative_mu': np.cumsum(mus).astype(np.float32)
                }
            plan_data['beams'][beam_name] = beam_data
        except (AttributeError, KeyError) as e:
            # Handle cases where expected tags are missing in a beam or control point
            print(f"Skipping beam {i} due to missing attribute: {e}")
            continue

    return plan_data
