import os
import logging
import yaml

logger = logging.getLogger(__name__)

VALID_ZERO_DOSE_REPORT_MODES = {"filtered", "raw", "both"}

DEFAULT_ZERO_DOSE_FILTER = {
    "enabled": True,
    "max_mu": 0.001,
    "machine_min_mu": 0.000452,
    "min_scan_speed_mm_s": 19000.0,
    "min_run_length": 2,
    "keep_first_zero_mu_spot": True,
    "boundary_holdoff_s": 0.0006,
    "post_minimal_dose_boundary_s": 0.001,
    "report_mode": "filtered",
}


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
    for key in (
        "REPORT_STYLE_SUMMARY",
        "EXPORT_PDF_REPORT",
        "EXPORT_REPORT_CSV",
        "SAVE_DEBUG_CSV",
    ):
        value = config.get(key)
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be a boolean")

    report_mode = config.get("ZERO_DOSE_REPORT_MODE")
    if report_mode not in VALID_ZERO_DOSE_REPORT_MODES:
        raise ValueError(
            "ZERO_DOSE_REPORT_MODE must be one of "
            f"{sorted(VALID_ZERO_DOSE_REPORT_MODES)}"
        )

    if config.get("ZERO_DOSE_MAX_MU") <= 0:
        raise ValueError("ZERO_DOSE_MAX_MU must be > 0")
    if config.get("ZERO_DOSE_MACHINE_MIN_MU") < 0:
        raise ValueError("ZERO_DOSE_MACHINE_MIN_MU must be >= 0")
    if config.get("ZERO_DOSE_MIN_SCAN_SPEED_MM_S") <= 0:
        raise ValueError("ZERO_DOSE_MIN_SCAN_SPEED_MM_S must be > 0")
    if config.get("ZERO_DOSE_MIN_RUN_LENGTH") < 1:
        raise ValueError("ZERO_DOSE_MIN_RUN_LENGTH must be >= 1")
    if config.get("ZERO_DOSE_BOUNDARY_HOLDOFF_S") < 0:
        raise ValueError("ZERO_DOSE_BOUNDARY_HOLDOFF_S must be >= 0")
    if config.get("ZERO_DOSE_POST_MINIMAL_DOSE_BOUNDARY_S") < 0:
        raise ValueError("ZERO_DOSE_POST_MINIMAL_DOSE_BOUNDARY_S must be >= 0")


def _parse_zero_dose_filter_config(yaml_data: dict) -> dict:
    section = yaml_data.get("zero_dose_filter") or {}
    if not isinstance(section, dict):
        raise ValueError("Invalid YAML structure: 'zero_dose_filter' must be a dict")

    merged = DEFAULT_ZERO_DOSE_FILTER.copy()
    merged.update(section)
    return {
        "ZERO_DOSE_FILTER_ENABLED": bool(merged["enabled"]),
        "ZERO_DOSE_MAX_MU": float(merged["max_mu"]),
        "ZERO_DOSE_MACHINE_MIN_MU": float(merged["machine_min_mu"]),
        "ZERO_DOSE_MIN_SCAN_SPEED_MM_S": float(merged["min_scan_speed_mm_s"]),
        "ZERO_DOSE_MIN_RUN_LENGTH": int(merged["min_run_length"]),
        "ZERO_DOSE_KEEP_FIRST_ZERO_MU_SPOT": bool(
            merged["keep_first_zero_mu_spot"]
        ),
        "ZERO_DOSE_BOUNDARY_HOLDOFF_S": float(merged["boundary_holdoff_s"]),
        "ZERO_DOSE_POST_MINIMAL_DOSE_BOUNDARY_S": float(
            merged["post_minimal_dose_boundary_s"]
        ),
        "ZERO_DOSE_REPORT_MODE": str(merged["report_mode"]).lower(),
    }


def parse_app_config(file_path: str) -> dict:
    """Parse and validate the legacy flat application config file."""
    config = _parse_key_value_config(
        file_path=file_path,
        allowed_keys=set(),
        string_keys=set(),
    )
    _validate_app_config(config)
    return config


def parse_yaml_config(file_path: str) -> dict:
    """Parse and validate the primary YAML application config file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)

    if not isinstance(yaml_data, dict) or "app" not in yaml_data:
        raise ValueError("Invalid YAML structure: missing 'app' section")

    app_section = yaml_data["app"]
    if not isinstance(app_section, dict):
        raise ValueError("Invalid YAML structure: 'app' must be a dict")

    report_style_summary = app_section.get("report_style_summary")
    export_pdf_report = app_section.get("export_pdf_report")
    export_report_csv = app_section.get("export_report_csv")
    save_debug_csv = app_section.get("save_debug_csv")

    if (
        report_style_summary is None
        or export_pdf_report is None
        or export_report_csv is None
        or save_debug_csv is None
    ):
        raise ValueError(
            "Missing required keys in app section: "
            "report_style_summary, export_pdf_report, export_report_csv, save_debug_csv"
        )

    config = {
        "REPORT_STYLE_SUMMARY": report_style_summary,
        "REPORT_STYLE": "summary" if report_style_summary else "classic",
        "EXPORT_PDF_REPORT": export_pdf_report,
        "EXPORT_REPORT_CSV": export_report_csv,
        "SAVE_DEBUG_CSV": save_debug_csv,
    }
    config.update(_parse_zero_dose_filter_config(yaml_data))

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
