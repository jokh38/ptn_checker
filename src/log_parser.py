import numpy as np
import os

PTN_COLUMN_COUNT = 8
BEAM_ON_THRESHOLD = 2**15 + 2**14
ALIGNMENT_TOLERANCE_MM = 1.0
ALIGNMENT_CONFIRM_MM = 5.0
N_PRE_BEAM_SAMPLES = 3
REQUIRED_CONFIG_KEYS = (
    "TIMEGAIN",
    "XPOSOFFSET",
    "YPOSOFFSET",
    "XPOSGAIN",
    "YPOSGAIN",
)
BASE_ARRAY_KEYS = (
    "time_ms",
    "x_raw",
    "y_raw",
    "x_size_raw",
    "y_size_raw",
    "dose1_au",
    "dose2_au",
    "layer_num",
    "beam_on_off",
    "x_mm",
    "y_mm",
    "x_size_mm",
    "y_size_mm",
)


def _require_config_params(config_params: dict) -> None:
    for key in REQUIRED_CONFIG_KEYS:
        if key not in config_params:
            raise KeyError(f"Error: Missing essential key '{key}' in config_params.")


def _select_arrays(arrays: dict, selector) -> dict:
    return {key: values[selector] for key, values in arrays.items()}


def _build_output_arrays(time_ms, data_2d_float, config_params):
    raw_x_col = data_2d_float[:, 0]
    raw_y_col = data_2d_float[:, 1]
    raw_x_size_col = data_2d_float[:, 2]
    raw_y_size_col = data_2d_float[:, 3]
    dose1_col = data_2d_float[:, 4]
    dose2_col = data_2d_float[:, 5]
    layer_num_col = data_2d_float[:, 6]
    beam_on_off_col = data_2d_float[:, 7]

    xpos_offset = float(config_params["XPOSOFFSET"])
    ypos_offset = float(config_params["YPOSOFFSET"])
    xpos_gain = float(config_params["XPOSGAIN"])
    ypos_gain = float(config_params["YPOSGAIN"])

    return {
        "time_ms": time_ms,
        "x_raw": raw_x_col,
        "y_raw": raw_y_col,
        "x_size_raw": raw_x_size_col,
        "y_size_raw": raw_y_size_col,
        "dose1_au": dose1_col,
        "dose2_au": dose2_col,
        "layer_num": layer_num_col,
        "beam_on_off": beam_on_off_col,
        "x_mm": (raw_x_col - xpos_offset) * xpos_gain,
        "y_mm": (raw_y_col - ypos_offset) * ypos_gain,
        "x_size_mm": raw_x_size_col * xpos_gain,
        "y_size_mm": raw_y_size_col * ypos_gain,
    }


def _with_cumulative_mu_and_aliases(arrays: dict) -> dict:
    arrays = arrays.copy()
    arrays["mu"] = np.cumsum(arrays["dose1_au"])
    arrays["x"] = arrays["x_mm"]
    arrays["y"] = arrays["y_mm"]
    return arrays


def _remove_alignment_outliers(
    arrays: dict,
    *,
    beam_on_mask,
    raw_y_col,
    ypos_offset,
    ypos_gain,
    alignment_y,
):
    beam_on_indices = np.where(beam_on_mask)[0]
    if len(beam_on_indices) == 0:
        return arrays

    first_beam_on_idx = beam_on_indices[0]
    pre_start = max(0, first_beam_on_idx - N_PRE_BEAM_SAMPLES)
    pre_end = first_beam_on_idx
    if pre_end <= pre_start:
        return arrays

    pre_beam_y_mm = (raw_y_col[pre_start:pre_end] - ypos_offset) * ypos_gain
    pre_beam_mean_y = np.mean(pre_beam_y_mm)
    if abs(pre_beam_mean_y - alignment_y) >= ALIGNMENT_CONFIRM_MM:
        return arrays

    n_outliers = 0
    for y_value in arrays["y_mm"]:
        if abs(y_value - pre_beam_mean_y) < ALIGNMENT_TOLERANCE_MM:
            n_outliers += 1
        else:
            break

    if n_outliers == 0:
        return arrays
    return _select_arrays(arrays, slice(n_outliers, None))


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
    _require_config_params(config_params)

    # Check if beam filtering is enabled
    filtered_beam_enabled = config_params.get('FILTERED_BEAM_ON_OFF', 'on').lower() == 'on'

    try:
        # 3. Read binary data using numpy, big-endian 2-byte unsigned integers
        raw_data_1d = np.fromfile(file_path, dtype='>u2')
    except Exception as e:
        raise IOError(f"Error reading binary data from {file_path}: {e}")

    # 4. Check if data can be reshaped (multiple of 8)
    if raw_data_1d.size % PTN_COLUMN_COUNT != 0:
        raise ValueError(
            f"Error: File data size ({raw_data_1d.size} shorts) "
            "is not a multiple of 8. Cannot reshape."
        )

    # Reshape to 2D array with 8 columns
    data_2d = raw_data_1d.reshape(-1, PTN_COLUMN_COUNT)

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

    raw_y_col = data_2d_float[:, 1]
    beam_on_off_col = data_2d_float[:, 7]
    ypos_offset = float(config_params['YPOSOFFSET'])
    ypos_gain = float(config_params['YPOSGAIN'])
    arrays = _build_output_arrays(
        time_column.flatten(),
        data_2d_float,
        config_params,
    )

    # 10. Conditionally filter data based on FILTERED_BEAM_ON_OFF setting
    if filtered_beam_enabled:
        # Filter data to include only "Beam On" states (beam_on_off == 1)
        beam_on_mask = beam_on_off_col > BEAM_ON_THRESHOLD
        arrays = _select_arrays(arrays, beam_on_mask)
    else:
        beam_on_mask = None

    # 10b. Filter leading beam-on samples stuck at scanning magnet alignment position
    # The first 1-2 beam-on samples often show Y at the magnet's alignment/transit
    # position (gantry-dependent) before the magnet settles to the planned spot.
    # These carry ~zero dose and create spurious max_abs_diff_y of 250-310 mm.
    alignment_y = config_params.get('ALIGNMENT_Y_POSITION')
    if alignment_y is not None and filtered_beam_enabled:
        alignment_y = float(alignment_y)
        arrays = _remove_alignment_outliers(
            arrays,
            beam_on_mask=beam_on_mask,
            raw_y_col=raw_y_col,
            ypos_offset=ypos_offset,
            ypos_gain=ypos_gain,
            alignment_y=alignment_y,
        )

    # 11. Filter out hardware default register values (position out of range)
    # Hardware defaults have x_raw > 65000; use min of config value and 60000
    # to ensure defaults are always caught regardless of config setting
    x_threshold = min(float(config_params.get('XTHRESHOLD', 60000)), 60000)
    y_threshold = min(float(config_params.get('YTHRESHOLD', 60000)), 60000)
    ypos_offset_val = float(config_params['YPOSOFFSET'])

    pos_valid_mask = (
        (arrays["x_raw"] <= x_threshold)
        & (arrays["y_raw"] >= (ypos_offset_val - y_threshold))
    )

    arrays = _select_arrays(arrays, pos_valid_mask)
    return _with_cumulative_mu_and_aliases(arrays)
