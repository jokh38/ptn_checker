import argparse
from datetime import date
import glob
import logging
import sys
import os
import pydicom
import numpy as np
from src.log_parser import parse_ptn_file
from src.dicom_parser import parse_dcm_file
from src.calculator import calculate_differences_for_layer
from src.report_generator import generate_report
from src.config_loader import parse_scv_init
from src.planrange_parser import parse_planrange_for_directory
from src.mu_correction import apply_mu_correction

logger = logging.getLogger(__name__)

def find_ptn_files(directory):
    ptn_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".ptn"):
                ptn_files.append(os.path.join(root, file))
    return ptn_files

def run_analysis(log_dir, dcm_file, output_dir, report_style='summary', report_name=None):
    """
    Runs the analysis on the given DICOM and PTN files and generates plot images.
    """
    if not os.path.isfile(dcm_file):
        raise FileNotFoundError(f"DICOM file not found: {dcm_file}")

    logger.info(f"Parsing DICOM file: {dcm_file}")
    try:
        plan_data_raw = parse_dcm_file(dcm_file)
    except Exception as e:
        raise ValueError(f"Failed to parse DICOM file: {e}")

    if not plan_data_raw or 'beams' not in plan_data_raw or not plan_data_raw['beams']:
        raise ValueError("Failed to parse DICOM file or it contains no beam data.")

    machine_name = plan_data_raw.get('machine_name', 'UNKNOWN')
    logger.info(f"Detected treatment machine: {machine_name}")

    config_file = f"scv_init_{machine_name.upper()}.txt"

    config_path = os.path.join(os.path.dirname(__file__) or '.', config_file)
    if not os.path.exists(config_path):
        available = glob.glob(os.path.join(os.path.dirname(__file__) or '.', "scv_init_*.txt"))
        logger.error(f"Config file not found: {config_path}. Available: {available}")
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        config = parse_scv_init(config_path)
    except Exception as e:
        raise ValueError(f"Failed to parse config file {config_path}: {e}")

    ptn_files = sorted(find_ptn_files(log_dir))
    planrange_lookup = parse_planrange_for_directory(log_dir)
    if not ptn_files:
        raise FileNotFoundError(f"No .ptn files found in directory {log_dir}")

    # Count expected layers across all beams
    expected_layer_count = sum(
        len(beam_data.get('layers', {}))
        for beam_data in plan_data_raw['beams'].values()
    )
    if len(ptn_files) != expected_layer_count:
        logger.warning(
            f"PTN file count ({len(ptn_files)}) does not match "
            f"expected layer count ({expected_layer_count})"
        )

    os.makedirs(output_dir, exist_ok=True)

    report_data = {
        '_patient_id': plan_data_raw.get('patient_id', ''),
        '_patient_name': plan_data_raw.get('patient_name', ''),
    }
    ptn_file_iter = iter(ptn_files)
    debug_csv_saved = False  # [debug] Flag to save CSV for only the first layer

    for beam_number, beam_data in plan_data_raw['beams'].items():
        beam_name = beam_data.get('name', f"Beam {beam_number}")
        report_data[beam_name] = {'layers': []}

        for layer_index, layer_data in beam_data.get('layers', {}).items():
            try:
                ptn_file = next(ptn_file_iter)
                # print(f"Processing {beam_name}, Layer {layer_index} with {os.path.basename(ptn_file)}")

                try:
                    log_data_raw = parse_ptn_file(ptn_file, config)
                    if not log_data_raw:
                        logger.warning(f"Could not parse PTN file or it is empty: {ptn_file}")
                        continue
                except (KeyError, ValueError, IOError) as e:
                    logger.error(f"Error parsing PTN file {ptn_file}: {e}")
                    continue

                abs_ptn = os.path.abspath(ptn_file)
                if abs_ptn in planrange_lookup:
                    range_info = planrange_lookup[abs_ptn]
                    apply_mu_correction(log_data_raw, range_info.energy, range_info.dose1_range_code)
                elif planrange_lookup:
                    logger.warning(f"No PlanRange entry for {ptn_file}, using uncorrected MU")

                try:
                    # [debug] Save CSV for the first processed layer only
                    save_csv_for_this_layer = not debug_csv_saved
                    csv_filepath = ""
                    if save_csv_for_this_layer:
                        csv_filepath = os.path.join(output_dir, f"debug_data_beam_{beam_number}_layer_{layer_index}.csv")

                    analysis_results = calculate_differences_for_layer(
                        layer_data,
                        log_data_raw,
                        save_to_csv=save_csv_for_this_layer,
                        csv_filename=csv_filepath
                    )
                    if save_csv_for_this_layer:
                        debug_csv_saved = True
                except (KeyError, ValueError, TypeError) as e:
                    logger.error(f"Error calculating differences for {beam_name}, Layer {layer_index}: {e}")
                    continue

                if 'error' in analysis_results:
                    logger.warning(f"Skipping layer due to error: {analysis_results['error']}")
                    continue

                report_data[beam_name]['layers'].append({
                    'layer_index': layer_index,
                    'results': analysis_results
                })

            except StopIteration:
                logger.warning(f"No more PTN files to process for layer {layer_index} of beam {beam_name}.")
                break

    if not any(data['layers'] for key, data in report_data.items() if not key.startswith('_')):
        raise ValueError("No analysis results were generated. Check logs for warnings.")

    logger.info(f"Generating PDF report in directory: {output_dir}")
    generate_report(report_data, output_dir, report_style=report_style, report_name=report_name)
    logger.info("Done.")

def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Analyze and compare radiotherapy plan and log files.")
    parser.add_argument("--log_dir", required=True,
                        help="Directory containing the PTN log files.")
    parser.add_argument("--dcm_file", required=True,
                        help="Path to the DICOM RTPLAN file.")
    parser.add_argument("-o", "--output", default="analysis_report",
                        help="Directory to save the output plot images.")
    parser.add_argument("--report-style", choices=["summary", "classic"],
                        default="summary",
                        help="Report format: 'summary' (one page per beam) or 'classic' (multi-page detailed).")
    args = parser.parse_args()

    # Derive report name from case ID (log directory basename) and today's date
    case_id = os.path.basename(os.path.normpath(args.log_dir))
    report_name = f"{case_id}_{date.today().isoformat()}"

    try:
        run_analysis(args.log_dir, args.dcm_file, args.output,
                     report_style=args.report_style, report_name=report_name)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()