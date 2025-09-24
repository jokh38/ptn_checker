import argparse
import sys
import os
import pydicom
from src.log_parser import parse_ptn_file
from src.dicom_parser import parse_dcm_file
from src.calculator import calculate_differences_for_layer
from src.report_generator import generate_report

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def find_ptn_files(directory):
    ptn_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".ptn"):
                ptn_files.append(os.path.join(root, file))
    return ptn_files

def run_analysis(log_dir, dcm_file, output_path):
    """
    Runs the analysis on the given DICOM and PTN files.
    """
    if not os.path.isfile(dcm_file):
        raise FileNotFoundError(f"DICOM file not found: {dcm_file}")

    print(f"Parsing DICOM file: {dcm_file}")
    plan_data = parse_dcm_file(dcm_file)
    if not plan_data or 'beams' not in plan_data or not plan_data['beams']:
        raise ValueError("Failed to parse DICOM file or it contains no beam data.")

    dcm = pydicom.dcmread(dcm_file)
    plan_data['patient_name'] = str(dcm.PatientName)
    plan_data['patient_id'] = dcm.PatientID

    ptn_files = sorted(find_ptn_files(log_dir))
    if not ptn_files:
        raise FileNotFoundError(f"No .ptn files found in directory {log_dir}")

    all_analysis_results = {}
    ptn_file_iter = iter(ptn_files)

    for beam_name, beam_data in plan_data['beams'].items():
        all_analysis_results[beam_name] = {}
        for layer_index, layer_data in beam_data['layers'].items():
            try:
                ptn_file = next(ptn_file_iter)
                print(f"Processing Beam {beam_name}, Layer {layer_index} with {os.path.basename(ptn_file)}")

                log_data = parse_ptn_file(ptn_file)
                if not log_data:
                    print(f"Warning: Could not parse PTN file or it is empty: {ptn_file}")
                    continue

                analysis_results = calculate_differences_for_layer(layer_data, log_data)
                all_analysis_results[beam_name][layer_index] = analysis_results

            except StopIteration:
                print(f"Warning: No more PTN files to process for layer {layer_index} of beam {beam_name}.")
                break

    if not all_analysis_results:
        raise ValueError("No analysis results were generated. Check logs for warnings.")

    print(f"Generating report at: {output_path}")
    generate_report(plan_data, all_analysis_results, output_path)
    print("Done.")

def main():
    parser = argparse.ArgumentParser(
        description="Analyze and compare radiotherapy plan and log files.")
    parser.add_argument("log_dir",
                        help="Directory containing the PTN log files.")
    parser.add_argument("dcm_file",
                        help="Path to the DICOM RTPLAN file.")
    parser.add_argument("-o", "--output", default="report.pdf",
                        help="Path to save the output PDF report.")
    args = parser.parse_args()

    try:
        run_analysis(args.log_dir, args.dcm_file, args.output)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
