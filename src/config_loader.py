import os
import logging

logger = logging.getLogger(__name__)


def _validate_settling_config(config: dict) -> None:
    threshold = config.get("SETTLING_THRESHOLD_MM")
    window = config.get("SETTLING_WINDOW_SAMPLES")
    consecutive = config.get("SETTLING_CONSECUTIVE_SAMPLES")

    if threshold is None or threshold <= 0:
        raise ValueError("SETTLING_THRESHOLD_MM must be > 0")
    if window is None or window <= 0 or int(window) != window:
        raise ValueError("SETTLING_WINDOW_SAMPLES must be a positive integer")
    if consecutive is None or consecutive <= 0 or int(consecutive) != consecutive:
        raise ValueError("SETTLING_CONSECUTIVE_SAMPLES must be a positive integer")
    if consecutive > window:
        raise ValueError("SETTLING_CONSECUTIVE_SAMPLES must be <= SETTLING_WINDOW_SAMPLES")


def parse_scv_init(file_path: str) -> dict:
    """
    Parses a scv_init file to extract configuration parameters.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    config = {}
    allowed_keys = {
        "XPOSGAIN",
        "YPOSGAIN",
        "XPOSOFFSET",
        "YPOSOFFSET",
        "TIMEGAIN",
        "FILTERED_BEAM_ON_OFF",
        "XTHRESHOLD",
        "YTHRESHOLD",
        "ALIGNMENT_Y_POSITION",
        "SETTLING_THRESHOLD_MM",
        "SETTLING_WINDOW_SAMPLES",
        "SETTLING_CONSECUTIVE_SAMPLES",
    }

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) == 2 and parts[0] in allowed_keys:
                key, value = parts
                if key == "FILTERED_BEAM_ON_OFF":
                    # Handle string values for this parameter
                    config[key] = value.lower()
                else:
                    try:
                        config[key] = float(value)
                    except ValueError:
                        logger.warning(
                            f"Ignoring non-numeric value '{value}' for key '{key}'"
                        )
    _validate_settling_config(config)
    return config
