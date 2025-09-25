import numpy as np
import os


def parse_ptn_file(file_path: str, config: dict) -> dict:
    """
    Parses a .ptn binary log file and applies coordinate transformation.

    Args:
        file_path: Path to the .ptn file.
        config: A dictionary containing the transformation parameters
                (XPOSGAIN, YPOSGAIN, XPOSOFFSET, YPOSOFFSET).

    Returns:
        A dictionary with transformed coordinates and MU data.
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

    raw_x_col = data_2d[:, 0].astype(np.float64) # 연산을 위해 float으로 변환
    raw_y_col = data_2d[:, 1].astype(np.float64)
    dose1_col = data_2d[:, 4]

    # 설정 값 가져오기
    x_gain = config.get('XPOSGAIN', 1.0)
    y_gain = config.get('YPOSGAIN', 1.0)
    x_offset = config.get('XPOSOFFSET', 0.0)
    y_offset = config.get('YPOSOFFSET', 0.0)

    # 좌표 변환 적용
    transformed_x = (raw_x_col - x_offset) * x_gain
    transformed_y = (raw_y_col - y_offset) * y_gain

    mu = np.cumsum(dose1_col)

    return {
        "x": transformed_x,
        "y": transformed_y,
        "mu": mu,
    }
