import numpy as np
import os


def parse_ptn_file(file_path: str, config_params: dict = None) -> dict:
    """
    Parses a .ptn binary log file into a dictionary of numpy arrays,
    optionally applying calibration parameters.

    Args:
        file_path: Path to the .ptn file.
        config_params: Optional dictionary containing calibration parameters:
                       'TIMEGAIN', 'XPOSOFFSET', 'YPOSOFFSET',
                       'XPOSGAIN', 'YPOSGAIN'.

    Returns:
        A dictionary containing processed data as numpy arrays.
        Includes raw and calibrated values if config_params are provided.

    Raises:
        FileNotFoundError: If file_path does not exist.
        ValueError: If the file data cannot be reshaped.
        KeyError: If config_params is provided but missing essential keys.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error: File not found at {file_path}")

    try:
        raw_data_1d = np.fromfile(file_path, dtype='>u2')
    except Exception as e:
        raise IOError(f"Error reading binary data from {file_path}: {e}")

    if raw_data_1d.size % 8 != 0:
        raise ValueError(
            f"Error: File data size ({raw_data_1d.size} shorts) "
            "is not a multiple of 8. Cannot reshape."
        )

    data_2d = raw_data_1d.reshape(-1, 8)
    data_2d_float = data_2d.astype(np.float32)

    raw_x_col = data_2d_float[:, 0]
    raw_y_col = data_2d_float[:, 1]
    dose1_col = data_2d_float[:, 4]

    mu = np.cumsum(dose1_col)

    # Base dictionary with raw data
    output_data = {
        "x_raw": raw_x_col,
        "y_raw": raw_y_col,
        "mu": mu,
        # For backward compatibility with old tests
        "x": raw_x_col,
        "y": raw_y_col,
    }

    # Apply calibrations if parameters are provided
    if config_params:
        required_keys = ['TIMEGAIN', 'XPOSOFFSET', 'YPOSOFFSET', 'XPOSGAIN', 'YPOSGAIN']
        for key in required_keys:
            if key not in config_params:
                raise KeyError(f"Error: Missing essential key '{key}' in config_params.")

        num_rows = data_2d_float.shape[0]
        time_gain = float(config_params['TIMEGAIN'])
        time_column = np.arange(num_rows, dtype=np.float32) * time_gain

        xpos_offset = float(config_params['XPOSOFFSET'])
        ypos_offset = float(config_params['YPOSOFFSET'])
        xpos_gain = float(config_params['XPOSGAIN'])
        ypos_gain = float(config_params['YPOSGAIN'])

        corrected_x_col = (raw_x_col - xpos_offset) * xpos_gain
        corrected_y_col = (raw_y_col - ypos_offset) * ypos_gain

        output_data.update({
            "time_ms": time_column,
            "x_mm": corrected_x_col,
            "y_mm": corrected_y_col,
        })

    return output_data
