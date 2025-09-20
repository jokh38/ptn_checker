import numpy as np
import os

def parse_ptn_file(file_path: str, config_params: dict) -> dict:
    """
    Parses a .ptn binary log file into a dictionary of numpy arrays.

    Args:
        file_path: Path to the .ptn file.
        config_params: Dictionary containing calibration parameters:
                       'TIMEGAIN', 'XPOSOFFSET', 'YPOSOFFSET', 
                       'XPOSGAIN', 'YPOSGAIN'.

    Returns:
        A dictionary where keys are descriptive strings (e.g., "time_ms", 
        "x_raw", "y_raw", "x_mm", "y_mm", etc.) and values are the 
        corresponding 1D numpy arrays.

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

    # 9. Return Data as dictionary of 1D arrays
    return {
        "time_ms": time_column.flatten(), # time_column is already 1D after reshape(-1,1).flatten() or direct
        "x_raw": raw_x_col,
        "y_raw": raw_y_col,
        "x_size_raw": raw_x_size_col,
        "y_size_raw": raw_y_size_col,
        "dose1_au": dose1_col,
        "dose2_au": dose2_col,
        "layer_num": layer_num_col, # Consider converting to int if appropriate: .astype(np.int32)
        "beam_on_off": beam_on_off_col, # Consider converting to int if appropriate
        "x_mm": corrected_x_col,
        "y_mm": corrected_y_col,
        "x_size_mm": corrected_x_size_col,
        "y_size_mm": corrected_y_size_col,
    }

def parse_mgn_file(file_path: str, config_params: dict) -> dict:
    """
    Placeholder for parsing .mgn binary log files.
    This function will be implemented later.
    """
    print(f"Placeholder: Would parse .mgn file {file_path} with params {config_params}")
    return {}

if __name__ == '__main__':
    pass
