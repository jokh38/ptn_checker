import os
import logging
import yaml

logger = logging.getLogger(__name__)

VALID_REPORT_STYLES = {"summary", "classic"}
VALID_TOGGLE_VALUES = {"on", "off"}


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
        raise ValueError(
            "SETTLING_CONSECUTIVE_SAMPLES must be <= SETTLING_WINDOW_SAMPLES"
        )


def _parse_key_value_config(
    file_path: str, allowed_keys: set[str], string_keys: set[str]
) -> dict:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    config = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) != 2 or parts[0] not in allowed_keys:
                continue

            key, value = parts
            if key in string_keys:
                config[key] = value.lower()
                continue

            try:
                config[key] = float(value)
            except ValueError:
                logger.warning(
                    "Ignoring non-numeric value '%s' for key '%s'",
                    value,
                    key,
                )

    return config


def _validate_app_config(config: dict) -> None:
    report_style = config.get("REPORT_STYLE")
    save_debug_csv = config.get("SAVE_DEBUG_CSV")

    if report_style not in VALID_REPORT_STYLES:
        raise ValueError(f"REPORT_STYLE must be one of {sorted(VALID_REPORT_STYLES)}")
    if save_debug_csv not in VALID_TOGGLE_VALUES:
        raise ValueError(f"SAVE_DEBUG_CSV must be one of {sorted(VALID_TOGGLE_VALUES)}")


def parse_app_config(file_path: str) -> dict:
    config = _parse_key_value_config(
        file_path=file_path,
        allowed_keys={"REPORT_STYLE", "SAVE_DEBUG_CSV"},
        string_keys={"REPORT_STYLE", "SAVE_DEBUG_CSV"},
    )
    _validate_app_config(config)
    return config


def parse_yaml_config(file_path: str) -> dict:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)

    if not isinstance(yaml_data, dict) or "app" not in yaml_data:
        raise ValueError("Invalid YAML structure: missing 'app' section")

    app_section = yaml_data["app"]
    if not isinstance(app_section, dict):
        raise ValueError("Invalid YAML structure: 'app' must be a dict")

    report_style = app_section.get("report_style")
    save_debug_csv = app_section.get("save_debug_csv")

    if report_style is None or save_debug_csv is None:
        raise ValueError(
            "Missing required keys in app section: report_style, save_debug_csv"
        )

    config = {
        "REPORT_STYLE": report_style,
        "SAVE_DEBUG_CSV": save_debug_csv,
    }

    _validate_app_config(config)
    return config


def parse_scv_init(file_path: str) -> dict:
    """
    Parses a scv_init file to extract configuration parameters.
    """
    config = _parse_key_value_config(
        file_path=file_path,
        allowed_keys={
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
        },
        string_keys={"FILTERED_BEAM_ON_OFF"},
    )
    _validate_settling_config(config)
    return config
