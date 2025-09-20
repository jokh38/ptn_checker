import numpy as np
import os


def parse_ptn_file(file_path: str) -> dict:
    """
    Parses a .ptn binary log file into a dictionary of numpy arrays.

    Args:
        file_path: Path to the .ptn file.

    Returns:
        A dictionary where keys are descriptive strings and values are the
        corresponding 1D numpy arrays.

    Raises:
        FileNotFoundError: If file_path does not exist.
        ValueError: If the file data cannot be reshaped.
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

    raw_x_col = data_2d[:, 0]
    raw_y_col = data_2d[:, 1]
    dose1_col = data_2d[:, 4]

    mu = np.cumsum(dose1_col)

    return {
        "x": raw_x_col,
        "y": raw_y_col,
        "mu": mu,
    }
