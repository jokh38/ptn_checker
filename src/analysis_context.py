import logging
import os

from src.config_loader import parse_scv_init
from src.dicom_parser import parse_dcm_file
from src.log_parser import parse_ptn_file
from src.mu_correction import apply_mu_correction


logger = logging.getLogger(__name__)


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(__file__))


def load_plan_and_machine_config(
    dcm_file: str,
    *,
    zero_dose_config: dict | None = None,
) -> tuple[dict, dict]:
    """Load DICOM plan data and the matching machine config for that plan."""
    if not os.path.isfile(dcm_file):
        raise FileNotFoundError(f"DICOM file not found: {dcm_file}")

    plan_data = parse_dcm_file(dcm_file, zero_dose_config=zero_dose_config)
    machine_name = plan_data.get("machine_name", "UNKNOWN").upper()
    config_path = os.path.join(_repo_root(), f"scv_init_{machine_name}.txt")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    return plan_data, parse_scv_init(config_path)


def parse_ptn_with_optional_mu_correction(
    ptn_file: str,
    config: dict,
    planrange_lookup: dict,
) -> dict:
    """Parse a PTN file and apply MU correction when matching range metadata exists."""
    log_data = parse_ptn_file(ptn_file, config)
    range_info = planrange_lookup.get(os.path.abspath(ptn_file))
    if range_info is not None:
        apply_mu_correction(log_data, range_info.energy, range_info.dose1_range_code)
    elif planrange_lookup:
        logger.warning("No PlanRange entry for %s, using uncorrected MU", ptn_file)
    return log_data
