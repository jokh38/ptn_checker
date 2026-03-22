import pydicom
import numpy as np
import os

from src.plan_timing import build_layer_time_trajectory
from src.config_loader import DEFAULT_ZERO_DOSE_FILTER


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


def _compute_spot_scan_speeds(positions_mm, segment_times_s):
    positions_mm = np.asarray(positions_mm, dtype=float)
    segment_times_s = np.asarray(segment_times_s, dtype=float)
    speeds = np.zeros(len(positions_mm), dtype=float)
    if len(positions_mm) <= 1:
        return speeds

    distances_mm = np.linalg.norm(positions_mm[1:] - positions_mm[:-1], axis=1)
    incoming_times_s = segment_times_s[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        speeds[1:] = np.divide(
            distances_mm,
            incoming_times_s,
            out=np.full_like(distances_mm, np.inf, dtype=float),
            where=incoming_times_s > 0,
        )
    return speeds


def _classify_transit_min_dose_spots(
    positions_mm,
    mu,
    segment_times_s,
    zero_dose_config=None,
):
    cfg = DEFAULT_ZERO_DOSE_FILTER.copy()
    if zero_dose_config:
        cfg.update(zero_dose_config)

    mu = np.asarray(mu, dtype=float)
    scan_speed = _compute_spot_scan_speeds(positions_mm, segment_times_s)
    if mu.size == 0:
        return np.zeros(0, dtype=bool), scan_speed

    max_mu = float(cfg["max_mu"])
    machine_min_mu = float(cfg["machine_min_mu"])
    min_speed = float(cfg["min_scan_speed_mm_s"])
    min_run_length = int(cfg["min_run_length"])
    keep_first_zero = bool(cfg["keep_first_zero_mu_spot"])

    candidate = (mu <= max_mu) & (scan_speed >= min_speed)
    transit = np.zeros_like(candidate, dtype=bool)

    idx = 0
    while idx < len(candidate):
        if not candidate[idx]:
            idx += 1
            continue
        start = idx
        while idx + 1 < len(candidate) and candidate[idx + 1]:
            idx += 1
        end = idx
        run_length = end - start + 1
        has_adjacent_treatment = (
            (start > 0 and not candidate[start - 1])
            or (end + 1 < len(candidate) and not candidate[end + 1])
        )
        if run_length >= min_run_length and has_adjacent_treatment:
            transit[start : end + 1] = True
        idx += 1

    machine_min_tol = max(1e-6, machine_min_mu * 0.05)
    isolated_machine_min = (
        candidate
        & (~transit)
        & np.isclose(mu, machine_min_mu, atol=machine_min_tol, rtol=0.0)
    )
    for idx in np.flatnonzero(isolated_machine_min):
        has_adjacent_treatment = (
            (idx > 0 and not candidate[idx - 1])
            or (idx + 1 < len(candidate) and not candidate[idx + 1])
        )
        if has_adjacent_treatment:
            transit[idx] = True

    if keep_first_zero:
        zero_mu_indices = np.flatnonzero(np.isclose(mu, 0.0, atol=1e-12, rtol=0.0))
        if zero_mu_indices.size > 0:
            transit[zero_mu_indices[0]] = False

    return transit, scan_speed


def _zero_dose_classifier_config(zero_dose_config: dict | None) -> dict | None:
    if not zero_dose_config:
        return None
    return {
        "max_mu": zero_dose_config.get(
            "ZERO_DOSE_MAX_MU",
            DEFAULT_ZERO_DOSE_FILTER["max_mu"],
        ),
        "machine_min_mu": zero_dose_config.get(
            "ZERO_DOSE_MACHINE_MIN_MU",
            DEFAULT_ZERO_DOSE_FILTER["machine_min_mu"],
        ),
        "min_scan_speed_mm_s": zero_dose_config.get(
            "ZERO_DOSE_MIN_SCAN_SPEED_MM_S",
            DEFAULT_ZERO_DOSE_FILTER["min_scan_speed_mm_s"],
        ),
        "min_run_length": zero_dose_config.get(
            "ZERO_DOSE_MIN_RUN_LENGTH",
            DEFAULT_ZERO_DOSE_FILTER["min_run_length"],
        ),
        "keep_first_zero_mu_spot": zero_dose_config.get(
            "ZERO_DOSE_KEEP_FIRST_ZERO_MU_SPOT",
            DEFAULT_ZERO_DOSE_FILTER["keep_first_zero_mu_spot"],
        ),
    }


def _decode_positions(pos_map_bytes):
    positions = []
    for idx in range(0, len(pos_map_bytes), 8):
        x_bytes = pos_map_bytes[idx + 2:idx + 4]
        y_bytes = pos_map_bytes[idx + 6:idx + 8]
        positions.append((F_SHI_spotP(x_bytes), F_SHI_spotP(y_bytes)))
    return np.array(positions)


def _decode_weights(mu_map_bytes):
    return np.array(
        [F_SHI_spotW(mu_map_bytes[idx:idx + 4]) for idx in range(0, len(mu_map_bytes), 4)]
    )


def _weights_to_mu(weights, total_mu_for_layer):
    total_weight = float(np.sum(weights))
    if total_weight > 0:
        return weights / total_weight * float(total_mu_for_layer)
    return np.zeros(len(weights), dtype=float)


def _build_layer_record(cp_start, cp_end, zero_dose_config):
    pos_map_bytes = cp_start[0x300b, 0x1094].value
    mu_map_bytes = cp_start[0x300b, 0x1096].value
    positions_array = _decode_positions(pos_map_bytes)
    weights = _decode_weights(mu_map_bytes)
    mus_array = _weights_to_mu(
        weights,
        cp_end.CumulativeMetersetWeight - cp_start.CumulativeMetersetWeight,
    )
    energy = float(getattr(cp_start, 'NominalBeamEnergy', 0.0))
    trajectory = build_layer_time_trajectory(
        positions_cm=positions_array * 0.1,
        mu=mus_array,
        energy=energy,
    )
    spot_is_transit_min_dose, spot_scan_speed_mm_s = _classify_transit_min_dose_spots(
        positions_mm=positions_array,
        mu=mus_array,
        segment_times_s=trajectory["segment_times_s"],
        zero_dose_config=_zero_dose_classifier_config(zero_dose_config),
    )
    return {
        'positions': positions_array,
        'mu': mus_array,
        'cumulative_mu': np.cumsum(mus_array),
        'energy': energy,
        'time_axis_s': trajectory['time_axis_s'],
        'trajectory_x_mm': trajectory['x_cm'] * 10.0,
        'trajectory_y_mm': trajectory['y_cm'] * 10.0,
        'segment_times_s': trajectory['segment_times_s'],
        'layer_doserate_mu_per_s': trajectory['layer_doserate_mu_per_s'],
        'total_time_s': trajectory['total_time_s'],
        'spot_is_transit_min_dose': spot_is_transit_min_dose,
        'spot_scan_speed_mm_s': spot_scan_speed_mm_s,
    }


def parse_dcm_file(file_path: str, zero_dose_config: dict | None = None) -> dict:
    """
    Parses a DICOM RTPLAN file to extract spot positions and MUs.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    plan = pydicom.dcmread(file_path)
    machine_name = getattr(plan.IonBeamSequence[0], 'TreatmentMachineName', 'UNKNOWN')
    patient_id = str(getattr(plan, 'PatientID', ''))
    patient_name = str(getattr(plan, 'PatientName', ''))
    plan_data = {
        'beams': {},
        'machine_name': machine_name,
        'patient_id': patient_id,
        'patient_name': patient_name,
    }
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
            plan_data['beams'][beam_number]['layers'][layer_index] = _build_layer_record(
                cp_start,
                cp_end,
                zero_dose_config,
            )
    return plan_data
