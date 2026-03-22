# Agent Runbook

## Project Goal

This repository analyzes radiotherapy plan data against PTN log data and generates PDF reports plus optional per-layer debug CSV files.

## Run

Use this command from the repository root:

```bash
python main.py \
  --log_dir ./Data_ex/1.2.840.113854.19.1.19271.1/2025042401440800 \
  --dcm_file ./plan.dcm \
  --output ./reports
```

## Config

- Report style (`summary` or `classic`) is configured in `config.yaml`.
- Debug CSV output is also controlled in `config.yaml`.

## Sample Data

Use these log datasets for testing:

- `G1`: `/home/jokh38/MOQUI_SMC/data/SHI_log/55758663`
- `G2`: `/home/jokh38/MOQUI_SMC/data/SHI_log/55061194`

For `G1`, point `--log_dir` at the parent case directory:

```bash
python main.py \
  --log_dir /home/jokh38/MOQUI_SMC/data/SHI_log/55758663 \
  --dcm_file /home/jokh38/MOQUI_SMC/data/SHI_log/55758663/RP.1.2.840.113854.116162735116359465886295179291233309871.1.dcm \
  --output ./output/55758663
```

When a case directory contains multiple beam delivery subdirectories, generate one combined PDF for all matched beams.

## Output

- Write generated outputs under `/output/ID` when using project test data.
- The example run command above writes reports to `./reports`.

## Validation Rules

- Explicitly label results as `component validated` or `end-to-end validated`.
- Do not claim end-to-end success from unit tests or component-only checks.
- Prefer `python -m pytest` over bare `pytest`.
- Report the exact verification commands used.

## Reporting

- Separate observations from assumptions.
- State known gaps, missing inputs, and unfinished modules explicitly.
- If results depend on local data availability, say what data was and was not present.
