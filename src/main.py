import argparse
import sys
import os
import pydicom
import glob
from src.log_parser import parse_ptn_file
from src.dicom_parser import parse_dcm_file
from src.calculator import calculate_differences_for_layer
from src.report_generator import generate_report
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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

    print(f"Parsing DICOM file: {args.dcm_file}")
    plan_data = parse_dcm_file(args.dcm_file)
    dcm = pydicom.dcmread(args.dcm_file)
    plan_data['patient_name'] = str(dcm.PatientName)
    plan_data['patient_id'] = dcm.PatientID

    all_analysis_results = {}

    # This is still a simplification. The real logic to match ptn files to
    # layers would be more complex, likely based on timestamps or filenames.
    # For now, we assume a single ptn file per layer, named in order.
    ptn_files = sorted(glob.glob(os.path.join(args.log_dir, "*.ptn")))

    if not ptn_files:
        print(f"Error: No .ptn files found in directory {args.log_dir}")
        return

    ptn_file_iter = iter(ptn_files)

    for beam_name, beam_data in plan_data['beams'].items():
        all_analysis_results[beam_name] = {}
        for layer_index, layer_data in beam_data['layers'].items():
            try:
                ptn_file = next(ptn_file_iter)
                print(f"Processing Beam {beam_name}, Layer {layer_index} with {os.path.basename(ptn_file)}")

                log_data = parse_ptn_file(ptn_file)

                analysis_results = calculate_differences_for_layer(
                    layer_data, log_data)

                all_analysis_results[beam_name][layer_index] = analysis_results

            except StopIteration:
                print(f"Warning: No more PTN files to process for layer {layer_index} of beam {beam_name}.")
                break

    print(f"Generating report at: {args.output}")
    generate_report(plan_data, all_analysis_results, args.output)
    print("Done.")


if __name__ == "__main__":
    main()
