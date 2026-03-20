"""
Parser for PlanRange.txt files.

Builds a lookup from absolute PTN file path to per-layer energy and
monitor range code, which are needed by :func:`mu_correction.apply_mu_correction`.
"""

import csv
import logging
import os
from typing import NamedTuple

logger = logging.getLogger(__name__)


class LayerRangeInfo(NamedTuple):
    energy: float
    dose1_range_code: int
    dose2_range_code: int
    plan_dose1_range_code: int
    plan_dose2_range_code: int


def parse_planrange_for_directory(log_dir: str) -> dict[str, LayerRangeInfo]:
    """
    Search *log_dir* and its immediate subdirectories for ``PlanRange.txt``
    files, parse them, and return a dict keyed by absolute PTN path.

    Returns:
        ``{'/abs/path/to/file.ptn': LayerRangeInfo(energy, dose1_range_code), ...}``
        Empty dict (with a warning) if no PlanRange.txt is found.
    """
    planrange_files: list[tuple[str, str]] = []  # (directory, filepath)

    # Check log_dir itself
    candidate = os.path.join(log_dir, 'PlanRange.txt')
    if os.path.isfile(candidate):
        planrange_files.append((log_dir, candidate))

    # Check immediate subdirectories
    try:
        for entry in os.scandir(log_dir):
            if entry.is_dir():
                candidate = os.path.join(entry.path, 'PlanRange.txt')
                if os.path.isfile(candidate):
                    planrange_files.append((entry.path, candidate))
    except OSError as e:
        logger.warning("Could not scan directory %s: %s", log_dir, e)

    if not planrange_files:
        logger.warning(
            "No PlanRange.txt found in %s or its subdirectories. "
            "MU correction will not be applied.", log_dir
        )
        return {}

    lookup: dict[str, LayerRangeInfo] = {}

    for parent_dir, pr_path in planrange_files:
        try:
            with open(pr_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header is None:
                    logger.warning("Empty PlanRange.txt: %s", pr_path)
                    continue

                for row_num, row in enumerate(reader, start=2):
                    try:
                        # CSV columns (0-indexed):
                        #  0: RESULT_ID
                        #  1: LAYER_NO
                        #  2: LAYER_ENERGY
                        #  3: PATIENT_ID
                        #  4: FLD_NO
                        #  5: DOSE1_RANGE
                        #  6: DOSE2_RANGE
                        #  7: PLAN_DOSE1_RANGE
                        #  8: PLAN_DOSE2_RANGE
                        #  9: SCAN_OUT_FL_NM
                        # 10: PLAN_SCAN_OUT_FL_NM
                        if len(row) < 10:
                            logger.warning(
                                "Skipping short row %d in %s (got %d columns)",
                                row_num, pr_path, len(row),
                            )
                            continue

                        energy = float(row[2])
                        dose1_range_code = int(row[5])
                        dose2_range_code = int(row[6])
                        plan_dose1_range_code = int(row[7])
                        plan_dose2_range_code = int(row[8])
                        ptn_filename = row[9].strip()

                        abs_ptn_path = os.path.abspath(
                            os.path.join(parent_dir, ptn_filename)
                        )
                        lookup[abs_ptn_path] = LayerRangeInfo(
                            energy=energy,
                            dose1_range_code=dose1_range_code,
                            dose2_range_code=dose2_range_code,
                            plan_dose1_range_code=plan_dose1_range_code,
                            plan_dose2_range_code=plan_dose2_range_code,
                        )
                    except (ValueError, IndexError) as e:
                        logger.warning(
                            "Skipping malformed row %d in %s: %s",
                            row_num, pr_path, e,
                        )
        except OSError as e:
            logger.warning("Could not read %s: %s", pr_path, e)

    logger.info(
        "Loaded PlanRange data for %d PTN files from %d PlanRange.txt file(s)",
        len(lookup), len(planrange_files),
    )
    return lookup
