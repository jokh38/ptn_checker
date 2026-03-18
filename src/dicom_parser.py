import pydicom
import numpy as np
import os


def F_SHI_spotW(spot_bytes):
    """Decode a SHI proprietary 4-byte spot weight from binary data.

    The SHI spot weight is encoded as a custom floating-point format in 4 bytes
    (little-endian). The bytes encode an exponent and mantissa:
      - byte 3 (x4): base-4 exponent offset by 64
      - byte 2 (x3): high bit selects a power-of-2 multiplier; low 7 bits
        contribute to the mantissa (fractional part at 2^-8)
      - byte 1 (x2): mantissa contribution at 2^-16
      - byte 0 (x1): mantissa contribution at 2^-24

    Args:
        spot_bytes: A 4-byte sequence in SHI proprietary binary format.

    Returns:
        The decoded spot weight as a float.
    """
    temp_spot_x1 = int.from_bytes(spot_bytes[0:1], 'little')
    temp_spot_x2 = int.from_bytes(spot_bytes[1:2], 'little')
    temp_spot_x3 = int.from_bytes(spot_bytes[2:3], 'little')
    temp_spot_x4 = int.from_bytes(spot_bytes[3:4], 'little')
    w_real = 2**(temp_spot_x3 // 128) * 4**(-64 + temp_spot_x4) * \
        (0.5 + (temp_spot_x3 % 128) / 2**8 + temp_spot_x2 / 2**16 +
         temp_spot_x1 / 2**24)
    return w_real


def F_SHI_spotP(spot_bytes):
    """Decode a SHI proprietary 2-byte spot position from binary data.

    The SHI spot position is encoded in 2 bytes (little-endian) using a custom
    sign-magnitude format with variable precision:
      - byte 1 (x2): bit 7 encodes sign (0=positive, 1=negative);
        bits 5-0 encode the magnitude exponent (det_pos_x2)
      - byte 0 (x1): encodes the fractional difference from the base magnitude

    The decoded position is in machine units (typically mm at isocenter).

    Args:
        spot_bytes: A 2-byte sequence in SHI proprietary binary format.

    Returns:
        The decoded spot position as a float (mm).
    """
    temp_spot_x1 = int.from_bytes(spot_bytes[0:1], 'little')
    temp_spot_x2 = int.from_bytes(spot_bytes[1:2], 'little')

    sign_pos_x2 = 1 if temp_spot_x2 < 128 else -1
    det_pos_x3 = temp_spot_x2 % 64
    if det_pos_x3 > 32:
        det_pos_x2 = -1
    else:
        det_pos_x2 = det_pos_x3
    det_pos_x1 = 128 - temp_spot_x1
    ind_helper_x1 = 8 - (2 * (det_pos_x2 + 1) + 1) + \
        abs(1 - (temp_spot_x1 // 128))
    real_diff = det_pos_x1 / (2**ind_helper_x1)
    x_real = sign_pos_x2 * (2**(2 * (det_pos_x2 + 1)) - real_diff)
    return x_real


def parse_dcm_file(file_path: str) -> dict:
    """
    Parses a DICOM RTPLAN file to extract spot positions and MUs.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    plan = pydicom.dcmread(file_path)
    machine_name = getattr(plan.IonBeamSequence[0], 'TreatmentMachineName', 'UNKNOWN')
    plan_data = {'beams': {}, 'machine_name': machine_name}
    if not hasattr(plan, 'IonBeamSequence'):
        raise AttributeError("DICOM file does not contain IonBeamSequence")

    for i, beam in enumerate(plan.IonBeamSequence):
        beam_description = getattr(beam, 'BeamDescription', '')
        beam_name = getattr(beam, 'BeamName', '')
        beam_number = getattr(beam, 'BeamNumber', i)
        if beam_description == "Site Setup" or beam_name == "SETUP":
            continue
        plan_data['beams'][beam_number] = {
            'name': beam_name,
            'layers': {}
        }
        ion_control_points = beam.IonControlPointSequence
        for i in range(0, len(ion_control_points), 2):
            cp_start = ion_control_points[i]
            if (i + 1) >= len(ion_control_points):
                continue
            cp_end = ion_control_points[i+1]
            layer_index = int(cp_start.ControlPointIndex)
            if (0x300b, 0x1094) not in cp_start:
                continue
            pos_map_bytes = cp_start[0x300b, 0x1094].value
            mu_map_bytes = cp_start[0x300b, 0x1096].value
            positions = []
            for j in range(0, len(pos_map_bytes), 8):
                x_bytes = pos_map_bytes[j+2:j+4]
                y_bytes = pos_map_bytes[j+6:j+8]
                x = F_SHI_spotP(x_bytes)
                y = F_SHI_spotP(y_bytes)
                positions.append((x, y))
            weights = []
            for j in range(0, len(mu_map_bytes), 4):
                weight = F_SHI_spotW(mu_map_bytes[j:j+4])
                weights.append(weight)
            total_mu_for_layer = (cp_end.CumulativeMetersetWeight -
                                  cp_start.CumulativeMetersetWeight)
            total_weight = sum(weights)
            if total_weight > 0:
                mus = [w / total_weight * total_mu_for_layer
                       for w in weights]
            else:
                mus = [0.0] * len(weights)
            plan_data['beams'][beam_number]['layers'][layer_index] = {
                'positions': np.array(positions),
                'mu': np.array(mus),
                'cumulative_mu': np.cumsum(mus)
            }
    return plan_data
