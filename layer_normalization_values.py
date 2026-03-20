import argparse
import csv
import math
import os
import statistics

from src.config_loader import parse_scv_init
from src.dicom_parser import parse_dcm_file
from src.log_parser import parse_ptn_file
from src.mu_correction import apply_mu_correction
from src.planrange_parser import parse_planrange_for_directory


def find_ptn_files(directory):
    ptn_files = []
    for root, _, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith(".ptn"):
                ptn_files.append(os.path.join(root, file_name))
    return sorted(ptn_files)


def format_range_difference(label_a, value_a, label_b, value_b):
    if value_a is None or value_b is None or value_a == value_b:
        return ""
    return f"{label_a}({value_a}) != {label_b}({value_b})"


def build_normalization_rows(log_dir, dcm_file):
    if not os.path.isfile(dcm_file):
        raise FileNotFoundError(f"DICOM file not found: {dcm_file}")

    plan_data = parse_dcm_file(dcm_file)
    machine_name = plan_data.get("machine_name", "UNKNOWN").upper()
    config_path = os.path.join(
        os.path.dirname(__file__) or ".", f"scv_init_{machine_name}.txt"
    )
    config = parse_scv_init(config_path)

    ptn_files = find_ptn_files(log_dir)
    if not ptn_files:
        raise FileNotFoundError(f"No .ptn files found in directory {log_dir}")

    planrange_lookup = parse_planrange_for_directory(log_dir)

    expected_layer_count = sum(
        len(beam_data.get("layers", {})) for beam_data in plan_data["beams"].values()
    )
    if len(ptn_files) < expected_layer_count:
        raise ValueError(
            f"PTN file count ({len(ptn_files)}) is smaller than expected layer count "
            f"({expected_layer_count})"
        )

    rows = []
    ptn_index = 0
    for beam_number, beam_data in plan_data["beams"].items():
        beam_name = beam_data.get("name", f"Beam {beam_number}")
        for layer_index, layer_data in beam_data.get("layers", {}).items():
            ptn_file = ptn_files[ptn_index]
            ptn_index += 1

            log_data = parse_ptn_file(ptn_file, config)
            range_info = planrange_lookup.get(os.path.abspath(ptn_file))
            if range_info is not None:
                apply_mu_correction(
                    log_data, range_info.energy, range_info.dose1_range_code
                )

            plan_mu = float(layer_data["mu"].sum())
            log_mu = float(log_data["mu"][-1]) if len(log_data["mu"]) else math.nan
            ratio = plan_mu / log_mu if log_mu and not math.isnan(log_mu) else math.nan

            rows.append(
                {
                    "machine": machine_name,
                    "beam_number": beam_number,
                    "beam_name": beam_name,
                    "layer_index": int(layer_index),
                    "DOSE1_RANGE": (
                        range_info.dose1_range_code if range_info is not None else ""
                    ),
                    "RANGE_PLAN_LOG_DIFF": (
                        format_range_difference(
                            "PLAN_DOSE1_RANGE",
                            range_info.plan_dose1_range_code,
                            "DOSE1_RANGE",
                            range_info.dose1_range_code,
                        )
                        if range_info is not None
                        else ""
                    ),
                    "RANGE_1_2_DIFF": (
                        format_range_difference(
                            "DOSE1_RANGE",
                            range_info.dose1_range_code,
                            "DOSE2_RANGE",
                            range_info.dose2_range_code,
                        )
                        if range_info is not None
                        else ""
                    ),
                    "plan_mu": plan_mu,
                    "log_mu": log_mu,
                    "normalization_ratio": ratio,
                    "ptn_file": os.path.abspath(ptn_file),
                }
            )

    return rows


def build_summary_rows(rows):
    grouped = {}
    for row in rows:
        key = (row["machine"], row["beam_name"])
        grouped.setdefault(key, []).append(row)

    summary_rows = []
    machine_groups = {}
    for (machine, beam_name), beam_rows in grouped.items():
        ratios = [
            row["normalization_ratio"]
            for row in beam_rows
            if not math.isnan(row["normalization_ratio"])
        ]
        plan_total = sum(row["plan_mu"] for row in beam_rows)
        log_total = sum(row["log_mu"] for row in beam_rows)
        summary_rows.append(
            {
                "scope": "beam",
                "machine": machine,
                "beam_name": beam_name,
                "layers": len(beam_rows),
                "plan_total_mu": plan_total,
                "log_total_mu": log_total,
                "total_ratio": plan_total / log_total if log_total else math.nan,
                "layer_ratio_mean": statistics.mean(ratios) if ratios else math.nan,
                "layer_ratio_std": (
                    statistics.pstdev(ratios) if len(ratios) > 1 else 0.0
                ),
                "layer_ratio_min": min(ratios) if ratios else math.nan,
                "layer_ratio_max": max(ratios) if ratios else math.nan,
            }
        )
        machine_groups.setdefault(machine, []).extend(beam_rows)

    for machine, machine_rows in machine_groups.items():
        ratios = [
            row["normalization_ratio"]
            for row in machine_rows
            if not math.isnan(row["normalization_ratio"])
        ]
        plan_total = sum(row["plan_mu"] for row in machine_rows)
        log_total = sum(row["log_mu"] for row in machine_rows)
        summary_rows.append(
            {
                "scope": "machine",
                "machine": machine,
                "beam_name": "",
                "layers": len(machine_rows),
                "plan_total_mu": plan_total,
                "log_total_mu": log_total,
                "total_ratio": plan_total / log_total if log_total else math.nan,
                "layer_ratio_mean": statistics.mean(ratios) if ratios else math.nan,
                "layer_ratio_std": (
                    statistics.pstdev(ratios) if len(ratios) > 1 else 0.0
                ),
                "layer_ratio_min": min(ratios) if ratios else math.nan,
                "layer_ratio_max": max(ratios) if ratios else math.nan,
            }
        )

    return summary_rows


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_analysis(
    log_dir,
    dcm_file,
    output_dir,
    layer_filename="layer_normalization_values.csv",
    summary_filename="machine_beam_summary.csv",
):
    os.makedirs(output_dir, exist_ok=True)

    layer_rows = build_normalization_rows(log_dir, dcm_file)
    summary_rows = build_summary_rows(layer_rows)

    layer_csv = os.path.join(output_dir, layer_filename)
    summary_csv = os.path.join(output_dir, summary_filename)

    write_csv(
        layer_csv,
        [
            "machine",
            "beam_number",
            "beam_name",
            "layer_index",
            "DOSE1_RANGE",
            "RANGE_PLAN_LOG_DIFF",
            "RANGE_1_2_DIFF",
            "plan_mu",
            "log_mu",
            "normalization_ratio",
            "ptn_file",
        ],
        layer_rows,
    )
    write_csv(
        summary_csv,
        [
            "scope",
            "machine",
            "beam_name",
            "layers",
            "plan_total_mu",
            "log_total_mu",
            "total_ratio",
            "layer_ratio_mean",
            "layer_ratio_std",
            "layer_ratio_min",
            "layer_ratio_max",
        ],
        summary_rows,
    )

    return layer_csv, summary_csv


def main():
    parser = argparse.ArgumentParser(
        description="Compute per-layer normalization values from RTPLAN and PTN data."
    )
    parser.add_argument("--log_dir", required=True, help="Directory containing PTN files")
    parser.add_argument("--dcm_file", required=True, help="Path to the RTPLAN DICOM")
    parser.add_argument(
        "--output", required=True, help="Directory where CSV outputs will be written"
    )
    parser.add_argument(
        "--layer_filename",
        default="layer_normalization_values.csv",
        help="Output filename for the per-layer CSV",
    )
    parser.add_argument(
        "--summary_filename",
        default="machine_beam_summary.csv",
        help="Output filename for the beam/machine summary CSV",
    )

    args = parser.parse_args()
    layer_csv, summary_csv = run_analysis(
        log_dir=args.log_dir,
        dcm_file=args.dcm_file,
        output_dir=args.output,
        layer_filename=args.layer_filename,
        summary_filename=args.summary_filename,
    )
    print(f"Wrote {layer_csv}")
    print(f"Wrote {summary_csv}")


if __name__ == "__main__":
    main()
