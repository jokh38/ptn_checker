# PTN Checker - Radiotherapy Plan and Log File Analyzer

A Python-based tool for analyzing and comparing radiotherapy treatment plans (DICOM RTPLAN files) against actual delivery log files (PTN format). The default comparison aligns reconstructed plan trajectories to rebased log time and can generate human-readable PDF reports plus machine-facing per-beam CSV summaries.

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
- **Report CSV Export**: Writes one CSV per beam with one row per analyzed layer for downstream program use
- **Machine-Specific Configuration**: Supports different treatment machines (G1, G2) with calibration parameters
- **Beam Filtering**: Optional filtering of log data based on beam on/off states
- **Multi-Beam and Multi-Layer Support**: Handles complex treatment plans with multiple beams and energy layers
- **Point Gamma Analysis**: Optional gamma index analysis with configurable fluence and distance thresholds
- **Zero Dose Filtering**: Filters out low-dose spots during analysis with configurable thresholds

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
| `pyyaml` | YAML configuration file parsing |

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

### Example

```bash
python main.py \
  --log_dir ./Data_ex/1.2.840.113854.19.1.19271.1/2025042401440800 \
  --dcm_file ./plan.dcm \
  --output ./reports
```

### Batch Processing

For processing multiple cases, use the provided batch script:

```bash
bash run_batch.sh
```

Edit `run_batch.sh` to customize the log directory, DICOM file path, and output location for your data.

### Output

The tool generates:
- **`{case_id}_{date}.pdf`**: Main analysis report (e.g., `2025042401440800_2025-01-15.pdf`)
  - Report name is derived from the log directory basename and current date
- **`<beam_name>_report_layers.csv`** (optional): Per-beam report CSV with one row per analyzed layer when `export_report_csv: true`
- **`debug_data_beam_<N>_layer_<M>.csv`** (optional): Debug CSV with interpolated and raw per-sample data when `save_debug_csv: true`

Legacy gamma normalization sweep scripts, standalone gamma debug exporters, and their separate report-generator stacks are not part of the active repository workflow.

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

### Configuration Files

The tool loads two configuration sources from the same directory as `main.py`:

- `config.yaml`: application-level output behavior (PDF report, report CSV, debug CSV)
- `scv_init_<machine>.txt`: machine-specific calibration and processing parameters

The treatment machine is detected from the DICOM file and mapped to the corresponding machine config:

- Machine **G1** → `scv_init_G1.txt`
- Machine **G2** → `scv_init_G2.txt`

## Configuration

### config.yaml

Application-level report and debug behavior is configured in `config.yaml`:

```yaml
app:
  report_style_summary: true
  report_detail_pdf: false
  export_pdf_report: true
  export_report_csv: false
  save_debug_csv: false
  analysis_mode: point_gamma

point_gamma:
  fluence_percent_threshold: 5.0
  distance_mm_threshold: 2.0
  lower_percent_fluence_cutoff: 10.0
  normalization_factor_by_machine:
    G1: 2.1384e-8
    G2: 2.0e-8

zero_dose_filter:
  enabled: true
  max_mu: 0.001
  machine_min_mu: 0.000452
  min_scan_speed_mm_s: 19000
  min_run_length: 2
  keep_first_zero_mu_spot: true
  boundary_holdoff_s: 0.0006
  post_minimal_dose_boundary_s: 0.001
  report_mode: "filtered"
```

| Parameter | Description |
|-----------|-------------|
| `report_style_summary` | `true` selects the current summary PDF layout; `false` maps to the legacy detailed PDF layout |
| `report_detail_pdf` | When `analysis_mode: point_gamma`, `true` generates an additional detailed PDF containing position comparison pages plus gamma analysis pages |
| `export_pdf_report` | `true` to generate the PDF report, `false` to skip PDF generation |
| `export_report_csv` | `true` to generate one per-beam layer-summary CSV for downstream programs |
| `save_debug_csv` | `true` to generate per-layer debug CSV files with low-level sample data |
| `analysis_mode` | Analysis mode: `point_gamma` for gamma index analysis, or omit for basic position comparison |

#### point_gamma Section

| Parameter | Description |
|-----------|-------------|
| `fluence_percent_threshold` | Fluence percentage threshold for gamma analysis (%) |
| `distance_mm_threshold` | Distance-to-agreement threshold for gamma analysis (mm) |
| `lower_percent_fluence_cutoff` | Lower fluence cutoff percentage for filtering low-dose regions |
| `normalization_factor_by_machine` | Machine-specific normalization factors (G1, G2) |

#### zero_dose_filter Section

| Parameter | Description |
|-----------|-------------|
| `enabled` | Enable/disable zero dose spot filtering |
| `max_mu` | Maximum MU threshold for considering a spot as "zero dose" |
| `machine_min_mu` | Machine-specific minimum MU value |
| `min_scan_speed_mm_s` | Minimum scan speed threshold (mm/s) |
| `min_run_length` | Minimum consecutive spots for a filter run |
| `keep_first_zero_mu_spot` | Keep the first zero-MU spot in a run |
| `boundary_holdoff_s` | Boundary holdoff time in seconds |
| `post_minimal_dose_boundary_s` | Post-minimal dose boundary time in seconds |
| `report_mode` | Reporting mode: `"filtered"` or `"all"` |

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
├── config.yaml               # App-level output/report configuration
├── LS_doserate.csv           # Dose rate lookup table by energy
├── scv_init_G1.txt           # Configuration for machine G1
├── scv_init_G2.txt           # Configuration for machine G2
├── requirements.txt          # Python dependencies
├── run_batch.sh              # Batch processing script
├── LOGFILE_SPEC.md           # PTN log file format specification
├── AGENTS.md                 # Agent runbook for AI development
├── src/
│   ├── __init__.py
│   ├── log_parser.py         # Parses binary PTN files
│   ├── dicom_parser.py       # Parses DICOM RTPLAN files
│   ├── plan_timing.py        # Builds time-domain trajectories from spot positions
│   ├── planrange_parser.py   # Parses PlanRange.txt for energy/range codes
│   ├── mu_correction.py      # Applies physics corrections to MU values
│   ├── calculator.py         # Calculates position differences
│   ├── analysis_context.py   # Orchestrates analysis workflow
│   ├── layer_normalization_values.py # Per-layer MU normalization factors
│   ├── ptn_discovery.py      # Discovers PTN files in log directories
│   ├── report_generator.py   # Generates PDF reports
│   ├── report_layout.py      # Base report layout definitions
│   ├── point_gamma_report_layout.py # Point gamma report layout
│   ├── point_gamma_workflow.py # Point gamma analysis workflow
│   ├── report_metrics.py     # Statistical metrics calculations
│   ├── report_constants.py   # Report display constants
│   ├── report_csv_exporter.py # Generates per-beam report CSV files
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
│   ├── test_config_loader.py     # Configuration loading tests
│   ├── test_analysis_context.py  # Analysis context tests
│   ├── test_layer_normalization_values.py # Layer normalization tests
│   ├── test_point_gamma_workflow.py # Point gamma workflow tests
│   └── test_report_csv_exporter.py # Report CSV exporter tests
├── docs/                     # Documentation directory
│   └── plan/                 # Implementation plans
├── output/                   # Generated analysis outputs
└── README.md                 # This file
```

## Workflow

1. **Load DICOM File**: Parse the RTPLAN file to extract planned beam positions, layers, and MU values
2. **Load Configuration**: Read app-level output settings from `config.yaml` and machine-specific calibration from the matching `scv_init` file
3. **Parse PlanRange**: Load PlanRange.txt to get per-layer energy and monitor range codes
4. **Find PTN Files**: Recursively search for `.ptn` log files in the specified directory
5. **Parse PTN Files**: For each layer, parse the corresponding PTN file with calibration
6. **Apply MU Correction**: Convert raw dose counts to physics-corrected MU values using energy-dependent factors
7. **Calculate Differences**: Sample the reconstructed plan trajectory on rebased log time and calculate position differences
8. **Apply Zero Dose Filter**: Filter out low-dose spots based on configurable thresholds
9. **Point Gamma Analysis** (optional): Calculate gamma indices if `analysis_mode: point_gamma`
10. **Statistical Analysis**: Fit Gaussian curves to difference histograms
11. **Generate Outputs**: Create PDF and/or per-beam report CSV files according to `config.yaml`

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

## Point Gamma Analysis

When `analysis_mode: point_gamma` is set in `config.yaml`, the tool performs gamma index analysis:

- Compares planned vs. delivered fluence at each point
- Calculates gamma index based on configurable distance and dose difference thresholds
- Filters low-fluence regions using `lower_percent_fluence_cutoff`
- Applies machine-specific normalization factors
- Generates point gamma visualization in the PDF report

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
- Unit tests for each module (log parser, DICOM parser, calculator, report generator, config loader, plan timing, MU correction, analysis context, layer normalization values, point gamma workflow, report CSV exporter)
- Integration tests for the main workflow
- Error handling tests (missing files, invalid data)
- Beam filtering tests for on/off state handling

## File Formats

### PTN Log Files

Binary format containing treatment delivery logs:
- 8 columns of data per record (big-endian unsigned 16-bit integers)
- Columns: RawX, RawY, RawXSize, RawYSize, Dose1, Dose2, LayerNum, BeamOnOff
- Beam On threshold: `beam_on_off > 49152` (filtered when `FILTERED_BEAM_ON_OFF=on`)

See `LOGFILE_SPEC.md` for detailed format specification.

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
