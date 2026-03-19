import numpy as np
import os

def parse_ptn_file(file_path: str, config_params: dict) -> dict:
    """
    Parses a .ptn binary log file into a dictionary of numpy arrays.
    Conditionally filters data based on FILTERED_BEAM_ON_OFF configuration.

    Args:
        file_path: Path to the .ptn file.
        config_params: Dictionary containing calibration parameters:
                       'TIMEGAIN', 'XPOSOFFSET', 'YPOSOFFSET',
                       'XPOSGAIN', 'YPOSGAIN', and optionally
                       'FILTERED_BEAM_ON_OFF' (defaults to 'on').

    Returns:
        A dictionary with the following keys (all values are 1D numpy arrays):
            - ``time_ms``      (float32): Elapsed time in ms (index * TIMEGAIN).
            - ``x_raw``        (float32): Raw X position register value.
            - ``y_raw``        (float32): Raw Y position register value.
            - ``x_size_raw``   (float32): Raw X beam size register value.
            - ``y_size_raw``   (float32): Raw Y beam size register value.
            - ``dose1_au``     (float32): Dose channel 1 (arbitrary units).
            - ``dose2_au``     (float32): Dose channel 2 (arbitrary units).
            - ``layer_num``    (float32): Layer number from the log.
            - ``beam_on_off``  (float32): Beam state flag.
            - ``x_mm``         (float32): Calibrated X position in mm.
            - ``y_mm``         (float32): Calibrated Y position in mm.
            - ``x_size_mm``    (float32): Calibrated X beam size in mm.
            - ``y_size_mm``    (float32): Calibrated Y beam size in mm.
            - ``mu``           (float32): Cumulative MU (alias for filtered cumulative dose).
            - ``x``            (float32): Alias for ``x_mm``.
            - ``y``            (float32): Alias for ``y_mm``.

        Data is filtered to include only "Beam On" states if
        FILTERED_BEAM_ON_OFF is set to "on", otherwise all data points.

    Raises:
        FileNotFoundError: If file_path does not exist.
        KeyError: If config_params is missing essential keys.
        ValueError: If the file data cannot be reshaped (not multiple of 8 shorts),
                    or if other data processing errors occur.
    """
    # 1. Check for file existence
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error: File not found at {file_path}")

    # 2. Check for essential config_params
    required_keys = ['TIMEGAIN', 'XPOSOFFSET', 'YPOSOFFSET', 'XPOSGAIN', 'YPOSGAIN']
    for key in required_keys:
        if key not in config_params:
            raise KeyError(f"Error: Missing essential key '{key}' in config_params.")

    # Check if beam filtering is enabled
    filtered_beam_enabled = config_params.get('FILTERED_BEAM_ON_OFF', 'on').lower() == 'on'

    try:
        # 3. Read binary data using numpy, big-endian 2-byte unsigned integers
        raw_data_1d = np.fromfile(file_path, dtype='>u2')
    except Exception as e:
        raise IOError(f"Error reading binary data from {file_path}: {e}")

    # 4. Check if data can be reshaped (multiple of 8)
    if raw_data_1d.size % 8 != 0:
        raise ValueError(
            f"Error: File data size ({raw_data_1d.size} shorts) "
            "is not a multiple of 8. Cannot reshape."
        )

    # Reshape to 2D array with 8 columns
    data_2d = raw_data_1d.reshape(-1, 8)

    # 5. Convert data type to float32
    data_2d_float = data_2d.astype(np.float32)

    # 6. Generate Time Column
    num_rows = data_2d_float.shape[0]
    time_gain = float(config_params['TIMEGAIN']) # Ensure float for calculation
    time_column = np.arange(num_rows, dtype=np.float32) * time_gain
    time_column = time_column.reshape(-1, 1)

    # 7. Combine Time and Data
    # Columns: Time, RawX, RawY, RawXSize, RawYSize, Dose1, Dose2, LayerNum, BeamOnOff
    data_with_time = np.hstack((time_column, data_2d_float))

    # Extract individual raw columns for clarity and calculations
    # Indices based on data_2d_float (original 8 columns after reshape)
    raw_x_col = data_2d_float[:, 0]
    raw_y_col = data_2d_float[:, 1]
    raw_x_size_col = data_2d_float[:, 2]
    raw_y_size_col = data_2d_float[:, 3]
    dose1_col = data_2d_float[:, 4]
    dose2_col = data_2d_float[:, 5]
    layer_num_col = data_2d_float[:, 6] # Should these be int? Kept as float32 for now.
    beam_on_off_col = data_2d_float[:, 7] # Should these be int?

    # 8. Apply Calibrations
    xpos_offset = float(config_params['XPOSOFFSET'])
    ypos_offset = float(config_params['YPOSOFFSET'])
    xpos_gain = float(config_params['XPOSGAIN'])
    ypos_gain = float(config_params['YPOSGAIN'])

    corrected_x_col = (raw_x_col - xpos_offset) * xpos_gain
    corrected_y_col = (raw_y_col - ypos_offset) * ypos_gain
    # As per C++ logFileLoadingThread, XPOSGAIN for XSize, YPOSGAIN for YSize
    corrected_x_size_col = raw_x_size_col * xpos_gain
    corrected_y_size_col = raw_y_size_col * ypos_gain

    # 9. Calculate cumulative MU from dose1_au only
    cumulative_mu = np.cumsum(dose1_col)

    # 10. Conditionally filter data based on FILTERED_BEAM_ON_OFF setting
    if filtered_beam_enabled:
        # Filter data to include only "Beam On" states (beam_on_off == 1)
        beam_on_mask = beam_on_off_col > 2**15 + 2**14  # Beam On if bit 15 and bit 14 are set

        # Apply mask to all data arrays
        filtered_time = time_column.flatten()[beam_on_mask]
        filtered_x_raw = raw_x_col[beam_on_mask]
        filtered_y_raw = raw_y_col[beam_on_mask]
        filtered_x_size_raw = raw_x_size_col[beam_on_mask]
        filtered_y_size_raw = raw_y_size_col[beam_on_mask]
        filtered_dose1 = dose1_col[beam_on_mask]
        filtered_dose2 = dose2_col[beam_on_mask]
        filtered_layer_num = layer_num_col[beam_on_mask]
        filtered_beam_on_off = beam_on_off_col[beam_on_mask]
        filtered_x_mm = corrected_x_col[beam_on_mask]
        filtered_y_mm = corrected_y_col[beam_on_mask]
        filtered_x_size_mm = corrected_x_size_col[beam_on_mask]
        filtered_y_size_mm = corrected_y_size_col[beam_on_mask]

        # Recalculate cumulative MU for filtered data (dose1 only)
        filtered_cumulative_mu = np.cumsum(filtered_dose1)
    else:
        # Use all data without filtering
        filtered_time = time_column.flatten()
        filtered_x_raw = raw_x_col
        filtered_y_raw = raw_y_col
        filtered_x_size_raw = raw_x_size_col
        filtered_y_size_raw = raw_y_size_col
        filtered_dose1 = dose1_col
        filtered_dose2 = dose2_col
        filtered_layer_num = layer_num_col
        filtered_beam_on_off = beam_on_off_col
        filtered_x_mm = corrected_x_col
        filtered_y_mm = corrected_y_col
        filtered_x_size_mm = corrected_x_size_col
        filtered_y_size_mm = corrected_y_size_col
        filtered_cumulative_mu = cumulative_mu

    # 10b. Filter leading beam-on samples stuck at scanning magnet alignment position
    # The first 1-2 beam-on samples often show Y at the magnet's alignment/transit
    # position (gantry-dependent) before the magnet settles to the planned spot.
    # These carry ~zero dose and create spurious max_abs_diff_y of 250-310 mm.
    ALIGNMENT_TOLERANCE_MM = 1.0   # max deviation from alignment to count as outlier
    ALIGNMENT_CONFIRM_MM = 5.0     # max deviation from config value to confirm pattern
    N_PRE_BEAM_SAMPLES = 3         # number of pre-beam-on samples to average

    alignment_y = config_params.get('ALIGNMENT_Y_POSITION')
    if alignment_y is not None and filtered_beam_enabled:
        alignment_y = float(alignment_y)

        # Find indices where beam transitions from off to on in the unfiltered data
        beam_on_indices = np.where(beam_on_mask)[0]

        if len(beam_on_indices) > 0:
            first_beam_on_idx = beam_on_indices[0]

            # Extract pre-beam-on Y samples (in raw units, convert to mm)
            pre_start = max(0, first_beam_on_idx - N_PRE_BEAM_SAMPLES)
            pre_end = first_beam_on_idx
            if pre_end > pre_start:
                pre_beam_y_mm = (raw_y_col[pre_start:pre_end] - ypos_offset) * ypos_gain
                pre_beam_mean_y = np.mean(pre_beam_y_mm)

                # Confirm this is actually the alignment pattern
                if abs(pre_beam_mean_y - alignment_y) < ALIGNMENT_CONFIRM_MM:
                    # Count leading beam-on samples that are still at alignment position
                    n_outliers = 0
                    for i in range(len(filtered_y_mm)):
                        if abs(filtered_y_mm[i] - pre_beam_mean_y) < ALIGNMENT_TOLERANCE_MM:
                            n_outliers += 1
                        else:
                            break  # magnet has settled

                    if n_outliers > 0:
                        # Slice all filtered arrays to remove alignment outliers
                        filtered_time = filtered_time[n_outliers:]
                        filtered_x_raw = filtered_x_raw[n_outliers:]
                        filtered_y_raw = filtered_y_raw[n_outliers:]
                        filtered_x_size_raw = filtered_x_size_raw[n_outliers:]
                        filtered_y_size_raw = filtered_y_size_raw[n_outliers:]
                        filtered_dose1 = filtered_dose1[n_outliers:]
                        filtered_dose2 = filtered_dose2[n_outliers:]
                        filtered_layer_num = filtered_layer_num[n_outliers:]
                        filtered_beam_on_off = filtered_beam_on_off[n_outliers:]
                        filtered_x_mm = filtered_x_mm[n_outliers:]
                        filtered_y_mm = filtered_y_mm[n_outliers:]
                        filtered_x_size_mm = filtered_x_size_mm[n_outliers:]
                        filtered_y_size_mm = filtered_y_size_mm[n_outliers:]
                        filtered_cumulative_mu = np.cumsum(filtered_dose1)

    # 11. Filter out hardware default register values (position out of range)
    # Hardware defaults have x_raw > 65000; use min of config value and 60000
    # to ensure defaults are always caught regardless of config setting
    x_threshold = min(float(config_params.get('XTHRESHOLD', 60000)), 60000)
    y_threshold = min(float(config_params.get('YTHRESHOLD', 60000)), 60000)
    ypos_offset_val = float(config_params['YPOSOFFSET'])

    pos_valid_mask = (filtered_x_raw <= x_threshold) & (filtered_y_raw >= (ypos_offset_val - y_threshold))

    filtered_time = filtered_time[pos_valid_mask]
    filtered_x_raw = filtered_x_raw[pos_valid_mask]
    filtered_y_raw = filtered_y_raw[pos_valid_mask]
    filtered_x_size_raw = filtered_x_size_raw[pos_valid_mask]
    filtered_y_size_raw = filtered_y_size_raw[pos_valid_mask]
    filtered_dose1 = filtered_dose1[pos_valid_mask]
    filtered_dose2 = filtered_dose2[pos_valid_mask]
    filtered_layer_num = filtered_layer_num[pos_valid_mask]
    filtered_beam_on_off = filtered_beam_on_off[pos_valid_mask]
    filtered_x_mm = filtered_x_mm[pos_valid_mask]
    filtered_y_mm = filtered_y_mm[pos_valid_mask]
    filtered_x_size_mm = filtered_x_size_mm[pos_valid_mask]
    filtered_y_size_mm = filtered_y_size_mm[pos_valid_mask]

    # Recalculate cumulative MU after position filtering (dose1 only)
    filtered_cumulative_mu = np.cumsum(filtered_dose1)

    # 12. Return Data as dictionary of 1D arrays (conditionally filtered)
    return {
        "time_ms": filtered_time,
        "x_raw": filtered_x_raw,
        "y_raw": filtered_y_raw,
        "x_size_raw": filtered_x_size_raw,
        "y_size_raw": filtered_y_size_raw,
        "dose1_au": filtered_dose1,
        "dose2_au": filtered_dose2,
        "layer_num": filtered_layer_num,
        "beam_on_off": filtered_beam_on_off,
        "x_mm": filtered_x_mm,
        "y_mm": filtered_y_mm,
        "x_size_mm": filtered_x_size_mm,
        "y_size_mm": filtered_y_size_mm,
        # Keys expected by calculator.py
        "mu": filtered_cumulative_mu,
        "x": filtered_x_mm,
        "y": filtered_y_mm,
    }
