import argparse
import csv
from datetime import date
import logging
import sys
import os
import numpy as np
from src.analysis_context import (
    load_plan_and_machine_config,
    parse_ptn_with_optional_mu_correction,
)
from src.calculator import calculate_differences_for_layer
from src.report_generator import generate_report
from src.report_csv_exporter import export_report_csv
from src.config_loader import parse_yaml_config
from src.planrange_parser import parse_planrange_for_directory
from src.ptn_discovery import find_ptn_files as discover_ptn_files

logger = logging.getLogger(__name__)


def derive_report_name(log_dir, today=None):
    """Build a case-level report name from the selected log directory."""
    report_date = today or date.today()
    case_id = os.path.basename(os.path.normpath(log_dir))
    return f"{case_id}_{report_date.isoformat()}"


def find_ptn_files(directory):
    return discover_ptn_files(directory)


def collect_ptn_delivery_groups(log_dir):
    groups = []

    direct_ptn_files = sorted(
        os.path.join(log_dir, entry.name)
        for entry in os.scandir(log_dir)
        if entry.is_file() and entry.name.endswith(".ptn")
    )
    if direct_ptn_files:
        groups.append(
            {
                "source_dir": log_dir,
                "ptn_files": direct_ptn_files,
                "planrange_lookup": parse_planrange_for_directory(log_dir),
                "beam_number": read_planinfo_beam_number(log_dir),
            }
        )

    subdirs = sorted(
        (entry.path for entry in os.scandir(log_dir) if entry.is_dir()),
        key=os.path.basename,
    )
    for subdir in subdirs:
        ptn_files = sorted(find_ptn_files(subdir))
        if not ptn_files:
            continue
        groups.append(
            {
                "source_dir": subdir,
                "ptn_files": ptn_files,
                "planrange_lookup": parse_planrange_for_directory(subdir),
                "beam_number": read_planinfo_beam_number(subdir),
            }
        )

    return groups


def read_planinfo_beam_number(directory):
    planinfo_path = os.path.join(directory, "PlanInfo.txt")
    if not os.path.isfile(planinfo_path):
        return None

    try:
        with open(planinfo_path, "r", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            for row in reader:
                if len(row) < 2:
                    continue
                if row[0].strip() == "DICOM_BEAM_NUMBER":
                    value = row[1].strip()
                    if value:
                        return int(value)
    except (OSError, ValueError) as exc:
        logger.warning("Failed to read PlanInfo beam number from %s: %s", planinfo_path, exc)

    return None


def match_delivery_groups_to_beams(plan_beams, delivery_groups):
    matched = {}
    remaining_beams = set(plan_beams.keys())

    for group in delivery_groups:
        beam_number = group.get("beam_number")
        if beam_number in remaining_beams:
            matched[beam_number] = group
            remaining_beams.remove(beam_number)

    for group in delivery_groups:
        if group in matched.values():
            continue
        matching_beams = [
            beam_number
            for beam_number in sorted(remaining_beams)
            if len(plan_beams[beam_number].get("layers", {})) == len(group["ptn_files"])
        ]
        if len(matching_beams) == 1:
            beam_number = matching_beams[0]
            matched[beam_number] = group
            remaining_beams.remove(beam_number)

    for group in delivery_groups:
        if group in matched.values():
            continue
        if not remaining_beams:
            break
        beam_number = min(remaining_beams)
        logger.warning(
            "Falling back to beam-order matching for %s (%d PTN files)",
            group["source_dir"],
            len(group["ptn_files"]),
        )
        matched[beam_number] = group
        remaining_beams.remove(beam_number)

    return matched


def run_analysis(log_dir, dcm_file, output_dir, report_name=None):
    """
    Runs the analysis on the given DICOM and PTN files and generates plot images.
    """
    app_config_path = os.path.join(os.path.dirname(__file__) or ".", "config.yaml")
    if not os.path.exists(app_config_path):
        raise FileNotFoundError(f"App config file not found: {app_config_path}")

    try:
        app_config = parse_yaml_config(app_config_path)
    except Exception as e:
        raise ValueError(f"Failed to parse config file: {e}")

    try:
        logger.info("Parsing DICOM file: %s", dcm_file)
        plan_data_raw, config = load_plan_and_machine_config(
            dcm_file,
            zero_dose_config=app_config,
        )
    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to load analysis inputs: {e}")

    if not plan_data_raw or "beams" not in plan_data_raw or not plan_data_raw["beams"]:
        raise ValueError("Failed to parse DICOM file or it contains no beam data.")

    machine_name = plan_data_raw.get("machine_name", "UNKNOWN")
    logger.info(f"Detected treatment machine: {machine_name}")
    analysis_config = {**config, **app_config}

    delivery_groups = collect_ptn_delivery_groups(log_dir)
    if not delivery_groups:
        raise FileNotFoundError(f"No .ptn files found in directory {log_dir}")

    treatment_beams = {
        beam_number: beam_data for beam_number, beam_data in plan_data_raw["beams"].items()
    }
    matched_groups = match_delivery_groups_to_beams(treatment_beams, delivery_groups)

    # Count expected layers across all beams
    expected_layer_count = sum(
        len(beam_data.get("layers", {}))
        for beam_data in treatment_beams.values()
    )
    actual_layer_count = sum(len(group["ptn_files"]) for group in delivery_groups)
    if actual_layer_count != expected_layer_count:
        logger.warning(
            f"PTN file count ({actual_layer_count}) does not match "
            f"expected layer count ({expected_layer_count})"
        )

    os.makedirs(output_dir, exist_ok=True)

    report_data = {
        "_patient_id": plan_data_raw.get("patient_id", ""),
        "_patient_name": plan_data_raw.get("patient_name", ""),
    }
    save_debug_csv = app_config["SAVE_DEBUG_CSV"]

    beam_processing_order = []
    for group in delivery_groups:
        for beam_number, matched_group in matched_groups.items():
            if matched_group is group:
                beam_processing_order.append(beam_number)
                break
    beam_processing_order.extend(
        beam_number
        for beam_number in treatment_beams
        if beam_number not in beam_processing_order
    )

    for beam_number in beam_processing_order:
        beam_data = treatment_beams[beam_number]
        beam_name = beam_data.get("name", f"Beam {beam_number}")
        report_data[beam_name] = {"beam_number": beam_number, "layers": []}
        matched_group = matched_groups.get(beam_number)
        if matched_group is None:
            logger.warning(
                "No PTN delivery group matched beam %s (%s)",
                beam_number,
                beam_name,
            )
            continue

        ptn_file_iter = iter(matched_group["ptn_files"])
        planrange_lookup = matched_group["planrange_lookup"]

        for layer_index, layer_data in beam_data.get("layers", {}).items():
            try:
                ptn_file = next(ptn_file_iter)

                try:
                    log_data_raw = parse_ptn_with_optional_mu_correction(
                        ptn_file,
                        config,
                        planrange_lookup,
                    )
                    if not log_data_raw:
                        logger.warning(
                            f"Could not parse PTN file or it is empty: {ptn_file}"
                        )
                        continue
                except (KeyError, ValueError, IOError) as e:
                    logger.error(f"Error parsing PTN file {ptn_file}: {e}")
                    continue

                try:
                    save_csv_for_this_layer = save_debug_csv
                    csv_filepath = ""
                    if save_csv_for_this_layer:
                        layer_number = layer_index // 2 + 1
                        csv_filepath = os.path.join(
                            output_dir,
                            f"debug_data_beam_{beam_number}_layer_{layer_number}.csv",
                        )

                    analysis_results = calculate_differences_for_layer(
                        layer_data,
                        log_data_raw,
                        save_to_csv=save_csv_for_this_layer,
                        csv_filename=csv_filepath,
                        config=analysis_config,
                    )
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(
                        f"Error calculating differences for {beam_name}, Layer {layer_index}: {e}"
                    )
                    continue

                if "error" in analysis_results:
                    logger.warning(
                        f"Skipping layer due to error: {analysis_results['error']}"
                    )
                    continue

                report_data[beam_name]["layers"].append(
                    {"layer_index": layer_index, "results": analysis_results}
                )

            except StopIteration:
                logger.warning(
                    f"No more PTN files to process for layer {layer_index} of beam {beam_name}."
                )
                break

    if not any(
        data["layers"] for key, data in report_data.items() if not key.startswith("_")
    ):
        raise ValueError("No analysis results were generated. Check logs for warnings.")

    if app_config["EXPORT_REPORT_CSV"]:
        logger.info(f"Generating report CSV files in directory: {output_dir}")
        export_report_csv(
            report_data,
            output_dir,
            report_mode=app_config["ZERO_DOSE_REPORT_MODE"],
        )

    if app_config["EXPORT_PDF_REPORT"]:
        logger.info(f"Generating PDF report in directory: {output_dir}")
        generate_report(
            report_data,
            output_dir,
            report_style=app_config["REPORT_STYLE"],
            report_name=report_name,
            report_mode=app_config["ZERO_DOSE_REPORT_MODE"],
            analysis_config=analysis_config,
        )
    logger.info("Done.")


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Analyze and compare radiotherapy plan and log files."
    )
    parser.add_argument(
        "--log_dir", required=True, help="Directory containing the PTN log files."
    )
    parser.add_argument(
        "--dcm_file", required=True, help="Path to the DICOM RTPLAN file."
    )
    parser.add_argument(
        "-o",
        "--output",
        default="analysis_report",
        help="Directory to save the output plot images.",
    )
    args = parser.parse_args()

    report_name = derive_report_name(args.log_dir)

    try:
        run_analysis(args.log_dir, args.dcm_file, args.output, report_name=report_name)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
