# Report CSV Export Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the old report-style enum config with explicit booleans and add a machine-facing per-beam/per-layer report CSV export that can run without generating a PDF.

**Architecture:** Parse the new YAML booleans in `src/config_loader.py`, then branch output generation in `main.py` so PDF and report-CSV are independently enabled. Build the new CSV from `report_data` in a dedicated exporter module so the CSV reuses the same effective per-layer metrics the report uses instead of debug per-sample internals.

**Tech Stack:** Python, `csv`, YAML, `unittest`, `unittest.mock`, `python -m pytest`

---

### Task 1: Add failing config parsing coverage

**Files:**
- Modify: `tests/test_config_loader.py`

**Step 1: Write the failing test**

Add coverage that `parse_yaml_config()` accepts:
- `report_style_summary: true`
- `export_pdf_report: false`
- `export_report_csv: true`
- `save_debug_csv: false`

and returns the matching parsed keys.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config_loader.py -q`
Expected: FAIL because the parser still expects `report_style` and string toggles.

**Step 3: Write minimal implementation**

Update `src/config_loader.py` to parse the new app keys and validate booleans plus derived report style mode.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config_loader.py -q`
Expected: PASS

### Task 2: Add failing output-flow coverage

**Files:**
- Modify: `tests/test_main.py`

**Step 1: Write the failing test**

Add coverage that:
- when `export_pdf_report: false`, `generate_report()` is not called
- when `export_report_csv: true`, one per-beam CSV is written
- each CSV has one row per layer and includes effective report metrics

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main.py -q`
Expected: FAIL because `main.py` always calls `generate_report()` and has no report CSV export.

**Step 3: Write minimal implementation**

Add a report CSV exporter and call it from `main.py`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_main.py -q`
Expected: PASS

### Task 3: Implement report CSV exporter

**Files:**
- Create: `src/report_csv_exporter.py`
- Modify: `main.py`
- Modify: `src/report_generator.py` or extract shared helpers only if needed

**Step 1: Write the failing test**

Add focused coverage for the exporter module if the `main.py` test alone is too indirect.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main.py tests/test_report_generator.py -q`
Expected: FAIL until exporter code exists.

**Step 3: Write minimal implementation**

Implement:
- per-beam file naming
- one row per layer
- effective metric selection using current `report_mode`
- pass/fail fields and sample-count metadata

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_main.py tests/test_report_generator.py -q`
Expected: PASS

### Task 4: Update default config and documentation

**Files:**
- Modify: `config.yaml`
- Modify: `README.md`

**Step 1: Write the failing test**

Use existing config-loader tests to reflect the shipped config shape.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config_loader.py -q`
Expected: FAIL until defaults and docs are aligned.

**Step 3: Write minimal implementation**

Update the repository config example and output documentation to describe:
- `report_style_summary`
- `export_pdf_report`
- `export_report_csv`
- `save_debug_csv`

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config_loader.py tests/test_main.py -q`
Expected: PASS

### Task 5: Final verification

**Files:**
- No code changes required

**Step 1: Run focused verification**

Run: `python -m pytest tests/test_config_loader.py tests/test_main.py -q`

**Step 2: Run broader regression verification**

Run: `python -m pytest tests/test_report_generator.py tests/test_calculator.py -q`

**Step 3: Report validation scope**

Label results as `component validated` unless a real CLI run on project data is also performed successfully end-to-end.
