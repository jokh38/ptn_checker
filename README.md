# PTN Checker - Radiotherapy Plan and Log File Analyzer

A Python-based tool for analyzing and comparing radiotherapy treatment plans (DICOM RTPLAN files) against actual delivery log files (PTN format). The default comparison aligns reconstructed plan trajectories to rebased log time and generates PDF reports with statistical analysis and visualization of position differences.

## Features

- **DICOM RTPLAN Parsing**: Extracts planned spot positions, MU, energy, and reconstructed time-domain trajectories from DICOM files
- **PTN Log File Parsing**: Reads binary treatment delivery log files with calibration parameters
- **Time-Based Alignment**: Reconstructs plan delivery time from spot motion and compares against rebased PTN log time
- **Position Difference Analysis**: Calculates differences between planned and actual beam positions after time-domain sampling
- **Statistical Analysis**: Performs Gaussian curve fitting on position difference histograms
- **PDF Report Generation**: Creates multi-page reports with:
  - Error bar plots showing position differences per layer
  - 2D position comparison plots for each layer
  - Organized by beam in a 3×2 grid layout
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
pip install numpy scipy matplotlib pydicom pytest
```

Or create a `requirements.txt` file with:

```
numpy
scipy
matplotlib
pydicom
pytest
```

Then install with:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Run the analysis from the command line:

```bash
python main.py --log_dir <path_to_ptn_files> --dcm_file <path_to_dicom_file> --output <output_directory>
```

### Arguments

- `--log_dir` (required): Directory containing `.ptn` log files. The tool searches recursively.
- `--dcm_file` (required): Path to the DICOM RTPLAN file (`.dcm`).
- `-o, --output` (optional): Directory to save the analysis report. Default: `analysis_report`

### Example

```bash
python main.py \
  --log_dir ./Data_ex/1.2.840.113854.19.1.19271.1/2025042401440800 \
  --dcm_file ./plan.dcm \
  --output ./reports
```

### Output

The tool generates:
- **`analysis_report.pdf`**: Main analysis report containing all plots organized by beam
- **`debug_data_beam_<N>_layer_<M>.csv`** (optional): Debug CSV file for the first processed layer containing interpolated and raw data

### Machine-Specific Configuration

The tool automatically detects the treatment machine from the DICOM file and loads the corresponding configuration file:

- Machine **G1** → `scv_init_G1.txt`
- Machine **G2** → `scv_init_G2.txt`

Configuration files must be in the same directory as `main.py`.

## Configuration

Configuration files (`scv_init_G1.txt`, `scv_init_G2.txt`) contain calibration parameters in the following format:

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

### Configuration Parameters

| Parameter | Description |
|-----------|-------------|
| `XPOSOFFSET`, `YPOSOFFSET` | Position offset values for calibration |
| `XPOSGAIN`, `YPOSGAIN` | Position gain values for calibration |
| `TIMEGAIN` | Time interval between data points (ms) |
| `FILTERED_BEAM_ON_OFF` | Set to `on` to filter for beam on/off states only, `off` to include all data |

## Project Structure

```
ptn_checker/
├── main.py                 # CLI entry point and orchestration
├── src/
│   ├── __init__.py
│   ├── log_parser.py       # Parses binary PTN files
│   ├── dicom_parser.py     # Parses DICOM RTPLAN files
│   ├── calculator.py        # Calculates position differences
│   ├── report_generator.py  # Generates PDF reports
│   └── config_loader.py    # Loads configuration files
├── tests/
│   ├── test_main.py
│   ├── test_log_parser.py
│   ├── test_dicom_parser.py
│   ├── test_calculator.py
│   ├── test_report_generator.py
│   └── test_config_loader.py
├── scv_init_G1.txt        # Configuration for machine G1
├── scv_init_G2.txt        # Configuration for machine G2
└── README.md              # This file
```

## Workflow

1. **Load DICOM File**: Parse the RTPLAN file to extract planned beam positions, layers, and MU values
2. **Load Configuration**: Read machine-specific calibration parameters
3. **Find PTN Files**: Recursively search for `.ptn` log files in the specified directory
4. **Parse PTN Files**: For each layer, parse the corresponding PTN file with calibration
5. **Calculate Differences**: Sample the reconstructed plan trajectory on rebased log time and calculate position differences
6. **Statistical Analysis**: Fit Gaussian curves to difference histograms
7. **Generate Report**: Create PDF with error bar plots and 2D position comparisons

## Testing

Run the test suite:

```bash
python -m pytest tests/
```

Run specific test files:

```bash
python -m pytest tests/test_main.py
python -m pytest tests/test_log_parser.py
python -m pytest tests/test_dicom_parser.py
```

Run with verbose output:

```bash
python -m pytest -v tests/
```

### Test Coverage

The test suite includes:
- Unit tests for each module (log parser, DICOM parser, calculator, report generator, config loader)
- Integration tests for the main workflow
- Error handling tests (missing files, invalid data)

## File Formats

### PTN Log Files

Binary format containing treatment delivery logs:
- 8 columns of data per record (big-endian unsigned 16-bit integers)
- Columns: RawX, RawY, RawXSize, RawYSize, Dose1, Dose2, LayerNum, BeamOnOff
- Automatically filtered based on beam on/off state if configured

### DICOM RTPLAN Files

Standard DICOM radiotherapy plan files containing:
- Ion beam sequence with control points
- Spot positions and weights for each energy layer
- Beam energy and cumulative meterset weights for timing reconstruction

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
