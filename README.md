# PTN Checker - Radiotherapy Plan and Log File Analyzer

A Python-based tool for analyzing and comparing radiotherapy treatment plans (DICOM RTPLAN files) against actual delivery log files (PTN format). The default comparison aligns reconstructed plan trajectories to rebased log time and generates PDF reports with statistical analysis and visualization of position differences.

## Features

- **DICOM RTPLAN Parsing**: Extracts planned spot positions, MU, energy, and reconstructed time-domain trajectories from DICOM files
- **PTN Log File Parsing**: Reads binary treatment delivery log files with calibration parameters
- **PlanRange Parsing**: Reads PlanRange.txt files to extract per-layer energy and monitor range codes for MU correction
- **MU Correction**: Applies energy-dependent physics corrections to convert raw dose counts to corrected MU values
- **Time-Based Alignment**: Reconstructs plan delivery time from spot motion and compares against rebased PTN log time
- **Position Difference Analysis**: Calculates differences between planned and actual beam positions after time-domain sampling
- **Statistical Analysis**: Performs Gaussian curve fitting on position difference histograms
- **PDF Report Generation**: Creates reports in two styles:
  - **Summary** (default): One page per beam with pass/fail indicators and key statistics
  - **Classic**: Multi-page detailed plots with error bars and 2D position comparisons
- **Machine-Specific Configuration**: Supports different treatment machines (G1, G2) with calibration parameters
- **Beam Filtering**: Optional filtering of log data based on beam on/off states
- **Multi-Beam and Multi-Layer Support**: Handles complex treatment plans with multiple beams and energy layers

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Dependencies

Install required Python packages:

```bash
pip install numpy scipy matplotlib pydicom
```

Or use the provided requirements.txt:

```bash
pip install -r requirements.txt
```

### Requirements

| Package | Purpose |
|---------|---------|
| `numpy` | Numerical operations |
| `scipy` | Curve fitting, PCHIP interpolation for MU correction |
| `matplotlib` | Plotting and PDF generation |
| `pydicom` | DICOM file parsing |

## Usage

### Basic Usage

Run the analysis from the command line:

```bash
python main.py --log_dir <path_to_ptn_files> --dcm_file <path_to_dicom_file> --output <output_directory>
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--log_dir` | Yes | Directory containing `.ptn` log files (searches recursively) |
| `--dcm_file` | Yes | Path to the DICOM RTPLAN file (`.dcm`) |
| `-o, --output` | No | Directory to save the analysis report. Default: `analysis_report` |
| `--report-style` | No | Report format: `summary` (one page per beam) or `classic` (multi-page detailed). Default: `summary` |

### Example

```bash
python main.py \
  --log_dir ./Data_ex/1.2.840.113854.19.1.19271.1/2025042401440800 \
  --dcm_file ./plan.dcm \
  --output ./reports \
  --report-style summary
```

### Output

The tool generates:
- **`{case_id}_{date}.pdf`**: Main analysis report (e.g., `2025042401440800_2025-01-15.pdf`)
  - Report name is derived from the log directory basename and current date
- **`debug_data_beam_<N>_layer_<M>.csv`** (optional): Debug CSV file for the first processed layer containing interpolated and raw data

### Report Styles

#### Summary Style (default)
- One page per beam
- Pass/fail indicators based on configurable thresholds
- Key statistics (mean, std, max) per layer
- Compact visualization suitable for quick review

#### Classic Style
- Multi-page detailed plots
- Error bar plots showing position differences per layer
- 2D position comparison plots for each layer
- Organized by beam in a 3×2 grid layout

### Machine-Specific Configuration

The tool automatically detects the treatment machine from the DICOM file and loads the corresponding configuration file:

- Machine **G1** → `scv_init_G1.txt`
- Machine **G2** → `scv_init_G2.txt`

Configuration files must be in the same directory as `main.py`.

## Configuration

### scv_init Files

Configuration files (`scv_init_G1.txt`, `scv_init_G2.txt`) contain calibration parameters:

```
# Position calibration
XPOSOFFSET    16384
YPOSOFFSET    16384
XPOSGAIN      0.010959
YPOSGAIN      0.0116412

# Time calibration
TIMEGAIN      0.0600745

# Beam filtering control
FILTERED_BEAM_ON_OFF    on
```

| Parameter | Description |
|-----------|-------------|
| `XPOSOFFSET`, `YPOSOFFSET` | Position offset values for calibration |
| `XPOSGAIN`, `YPOSGAIN` | Position gain values for calibration |
| `TIMEGAIN` | Time interval between data points (ms) |
| `FILTERED_BEAM_ON_OFF` | Set to `on` to filter for beam on/off states only, `off` to include all data |

### LS_doserate.csv

Dose rate lookup table indexed by energy (MeV). Used by the plan timing module to determine layer dose rates. Must be in the project root directory.

### PlanRange.txt

CSV file containing per-layer energy and monitor range codes. Expected columns:
- `LAYER_ENERGY`: Nominal beam energy for the layer
- `DOSE1_RANGE`: Monitor range code (2-5) for dose scaling
- `SCAN_OUT_FL_NM`: PTN filename for the layer

Used by the MU correction module to apply physics corrections.

## Project Structure

```
ptn_checker/
├── main.py                    # CLI entry point and orchestration
├── LS_doserate.csv           # Dose rate lookup table by energy
├── scv_init_G1.txt           # Configuration for machine G1
├── scv_init_G2.txt           # Configuration for machine G2
├── requirements.txt          # Python dependencies
├── src/
│   ├── __init__.py
│   ├── log_parser.py         # Parses binary PTN files
│   ├── dicom_parser.py       # Parses DICOM RTPLAN files
│   ├── plan_timing.py        # Builds time-domain trajectories from spot positions
│   ├── planrange_parser.py   # Parses PlanRange.txt for energy/range codes
│   ├── mu_correction.py      # Applies physics corrections to MU values
│   ├── calculator.py         # Calculates position differences
│   ├── report_generator.py   # Generates PDF reports
│   └── config_loader.py      # Loads configuration files
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Shared test fixtures and helpers
│   ├── test_main.py          # Integration tests
│   ├── test_log_parser.py    # PTN parsing tests
│   ├── test_dicom_parser.py  # DICOM parsing tests
│   ├── test_plan_timing.py   # Plan timing module tests
│   ├── test_calculator.py    # Position difference calculation tests
│   ├── test_report_generator.py  # Report generation tests
│   ├── test_beam_filtering.py    # Beam on/off filtering tests
│   └── test_config_loader.py     # Configuration loading tests
└── README.md                 # This file
```

## Workflow

1. **Load DICOM File**: Parse the RTPLAN file to extract planned beam positions, layers, and MU values
2. **Load Configuration**: Read machine-specific calibration parameters from scv_init file
3. **Parse PlanRange**: Load PlanRange.txt to get per-layer energy and monitor range codes
4. **Find PTN Files**: Recursively search for `.ptn` log files in the specified directory
5. **Parse PTN Files**: For each layer, parse the corresponding PTN file with calibration
6. **Apply MU Correction**: Convert raw dose counts to physics-corrected MU values using energy-dependent factors
7. **Calculate Differences**: Sample the reconstructed plan trajectory on rebased log time and calculate position differences
8. **Statistical Analysis**: Fit Gaussian curves to difference histograms
9. **Generate Report**: Create PDF with plots and statistics in selected style

## MU Correction

The MU correction module (`mu_correction.py`) applies a chain of corrections to convert raw `dose1_au` counts from PTN files into physically corrected MU values:

```
corrected_mu = dose1_au
               × proton_per_dose_factor(energy)
               × dose_per_mu_count_factor(energy)
               × monitor_range_factor(code)
               ÷ dose_dividing_factor
```

This correction chain is adapted from the `mqi_interpreter` reference implementation and uses PCHIP interpolation for smooth energy-dependent factors across the 70-230 MeV range.

## Testing

Run the test suite:

```bash
python -m pytest tests/
```

Run specific test files:

```bash
python -m pytest tests/test_main.py
python -m pytest tests/test_plan_timing.py
python -m pytest tests/test_mu_correction.py -v
```

Run with verbose output:

```bash
python -m pytest -v tests/
```

### Test Coverage

The test suite includes:
- Unit tests for each module (log parser, DICOM parser, calculator, report generator, config loader, plan timing, MU correction)
- Integration tests for the main workflow
- Error handling tests (missing files, invalid data)
- Beam filtering tests for on/off state handling

## File Formats

### PTN Log Files

Binary format containing treatment delivery logs:
- 8 columns of data per record (big-endian unsigned 16-bit integers)
- Columns: RawX, RawY, RawXSize, RawYSize, Dose1, Dose2, LayerNum, BeamOnOff
- Beam On threshold: `beam_on_off > 49152` (filtered when `FILTERED_BEAM_ON_OFF=on`)

### DICOM RTPLAN Files

Standard DICOM radiotherapy plan files containing:
- Ion beam sequence with control points
- Spot positions and weights for each energy layer
- Beam energy and cumulative meterset weights for timing reconstruction

### PlanRange.txt Files

CSV format with columns:
- `RESULT_ID`, `LAYER_NO`, `LAYER_ENERGY`, `PATIENT_ID`, `FLD_NO`
- `DOSE1_RANGE`, `DOSE2_RANGE` - Monitor range codes
- `PLAN_DOSE1_RANGE`, `PLAN_DOSE2_RANGE`
- `SCAN_OUT_FL_NM` - PTN filename for the layer
- `PLAN_SCAN_OUT_FL_NM`

## Troubleshooting

### Common Issues

**Error: "DICOM file not found"**
- Verify the path to the DICOM file is correct

**Error: "No .ptn files found"**
- Check that the log directory contains `.ptn` files
- Ensure the directory path is correct

**Error: "Could not determine config file for machine"**
- Verify the machine name in the DICOM file matches `G1` or `G2`
- Ensure the corresponding `scv_init_G1.txt` or `scv_init_G2.txt` exists

**Error: "No analysis results were generated"**
- Check that PTN files are not empty
- Verify that the DICOM file contains valid beam data
- Review warning messages in the console for parsing errors

**Warning: "No PlanRange entry for {ptn_file}"**
- PlanRange.txt is missing or incomplete for the log directory
- MU correction will not be applied; raw MU values will be used

**Warning: "PTN file count does not match expected layer count"**
- Some layers may be missing PTN files
- Check that all expected PTN files are present in the log directory

## License

This project is part of the MOQUI_SMC system. Please refer to the project repository for licensing information.

## Contributing

When contributing:
1. Add tests for new functionality
2. Ensure all tests pass (`python -m pytest tests/`)
3. Follow the existing code style and documentation patterns
4. Update this README if adding new features

## Support

For issues or questions, please refer to the project repository or contact the development team.
