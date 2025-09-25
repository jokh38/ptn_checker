import argparse
import sys
import os
import pydicom
import numpy as np
from src.log_parser import parse_ptn_file
from src.dicom_parser import parse_dcm_file
from src.calculator import calculate_differences_for_layer
from src.report_generator import generate_report
from src.config_loader import parse_scv_init

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def find_ptn_files(directory):
    ptn_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".ptn"):
                ptn_files.append(os.path.join(root, file))
    return ptn_files

def run_analysis(log_dir, dcm_file, output_dir):
    """
    Runs the analysis on the given DICOM and PTN files and generates plot images.
    """
    if not os.path.isfile(dcm_file):
        raise FileNotFoundError(f"DICOM file not found: {dcm_file}")

    print(f"Parsing DICOM file: {dcm_file}")
    plan_data_raw = parse_dcm_file(dcm_file)
    if not plan_data_raw or 'beams' not in plan_data_raw or not plan_data_raw['beams']:
        raise ValueError("Failed to parse DICOM file or it contains no beam data.")

    machine_name = plan_data_raw.get('machine_name', 'UNKNOWN')
    config_file_map = {"G1": "scv_init_G1.txt", "G2": "scv_init_G2.txt"}
    config_file = config_file_map.get(machine_name.upper(), None)

    if not config_file:
        raise ValueError(f"Could not determine config file for machine: {machine_name}")

    config_path = os.path.join(os.path.dirname(__file__) or '.', config_file)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config = parse_scv_init(config_path)

    ptn_files = sorted(find_ptn_files(log_dir))
    if not ptn_files:
        raise FileNotFoundError(f"No .ptn files found in directory {log_dir}")

    # Data structures for the new report generator
    mean_diffs = {'x': [], 'y': []}
    std_diffs = {'x': [], 'y': []}
    all_plan_positions = []
    all_log_positions = []

    ptn_file_iter = iter(ptn_files)

    for beam_number, beam_data in plan_data_raw['beams'].items():
        for layer_index, layer_data in beam_data['layers'].items():
            try:
                ptn_file = next(ptn_file_iter)
                print(f"Processing Beam {beam_number}, Layer {layer_index} with {os.path.basename(ptn_file)}")

                log_data_raw = parse_ptn_file(ptn_file, config)
                if not log_data_raw:
                    print(f"Warning: Could not parse PTN file or it is empty: {ptn_file}")
                    continue

                analysis_results = calculate_differences_for_layer(layer_data, log_data_raw)

                if 'error' in analysis_results:
                    print(f"Skipping layer due to error: {analysis_results['error']}")
                    continue

                # Aggregate data for plots
                mean_diffs['x'].append(analysis_results['mean_diff_x'])
                mean_diffs['y'].append(analysis_results['mean_diff_y'])
                std_diffs['x'].append(analysis_results['std_diff_x'])
                std_diffs['y'].append(analysis_results['std_diff_y'])
                all_plan_positions.append(analysis_results['plan_positions'])
                all_log_positions.append(analysis_results['log_positions'])

            except StopIteration:
                print(f"Warning: No more PTN files to process for layer {layer_index} of beam {beam_number}.")
                break

    if not all_plan_positions:
        raise ValueError("No analysis results were generated. Check logs for warnings.")

    # Prepare data dictionaries for the report generator
    final_plan_data = {
        'mean_diff': {'x': np.array(mean_diffs['x']), 'y': np.array(mean_diffs['y'])},
        'std_diff': {'x': np.array(std_diffs['x']), 'y': np.array(std_diffs['y'])},
        'positions': all_plan_positions
    }
    final_log_data = {'positions': all_log_positions}

    print(f"Generating reports in directory: {output_dir}")
    generate_report(final_plan_data, final_log_data, output_dir)
    print("Done.")

def main():
    parser = argparse.ArgumentParser(
        description="Analyze and compare radiotherapy plan and log files.")
    parser.add_argument("--log_dir", required=True,
                        help="Directory containing the PTN log files.")
    parser.add_argument("--dcm_file", required=True,
                        help="Path to the DICOM RTPLAN file.")
    parser.add_argument("-o", "--output", default="analysis_report",
                        help="Directory to save the output plot images.")
    args = parser.parse_args()

    try:
        run_analysis(args.log_dir, args.dcm_file, args.output)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()