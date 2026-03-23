# Main Gamma Analysis Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the new fluence-map gamma analysis feature from `.worktrees/fluence-gamma` into `main`, controlled by a centralized configuration flag rather than a CLI switch.

**Architecture:** Keep `main.py` as the single application entrypoint and route execution by the centralized YAML key `app.analysis_mode`. Reuse the existing gamma-capable path already present in `main`, then merge the remaining worktree-specific additions: machine-specific normalization from centralized config and the revised gamma PDF layout with four layer figures per page.

**Tech Stack:** Python, pytest, matplotlib, numpy, YAML config loading, existing PTN/DICOM parsing pipeline

---

## Context

The repository now has two relevant states:

- `main` already contains the gamma analysis execution path, gamma workflow modules, and gamma PDF generation.
- `.worktrees/fluence-gamma` contains newer feature work that is not yet fully reflected in `main`:
  - centralized machine-specific normalization via `gamma.normalization_factor_by_machine`
  - runtime resolution of `GAMMA_NORMALIZATION_FACTOR` after machine detection
  - revised gamma PDF pagination: 4 layer figures per page, each figure containing the 3 panels `plan fluence`, `log fluence`, `gamma map`
  - updated gamma criteria configured as `5% / 2 mm`

The implementation should consolidate those differences into `main` and preserve the centralized-config-controlled analysis-mode switch.

## Target Behavior

### Centralized Config Routing

The analysis mode must be controlled through `config.yaml`, not CLI flags.

Expected config shape:

```yaml
app:
  analysis_mode: trajectory  # or gamma

gamma:
  fluence_percent_threshold: 5.0
  distance_mm_threshold: 2.0
  lower_percent_fluence_cutoff: 10.0
  grid_resolution_mm: 3.0
  spot_tolerance_mm: 1.0
  require_planrange_mu_correction: true
  allow_relative_fluence_fallback: true
  use_gaussian_spot_model: true
  gaussian_sigma_mm: 3.0
  map_margin_mm: 2.0
  normalization_factor_by_machine:
    G1: 5.5e-7
    G2: 5.0e-7
```

Execution rules:

- `app.analysis_mode: trajectory`
  - run the existing position-difference analysis path
  - generate trajectory-style reports/CSV as currently supported
- `app.analysis_mode: gamma`
  - run fluence-map gamma analysis
  - generate gamma PDF report
  - skip unsupported trajectory-only CSV export paths or log an explicit warning

### Machine-Specific Gamma Normalization

When `analysis_mode` is `gamma`:

1. Parse `gamma.normalization_factor_by_machine` from centralized config.
2. Detect the treatment machine from the DICOM plan.
3. Resolve the matching normalization factor at runtime.
4. Inject that resolved factor into the merged runtime analysis config as `GAMMA_NORMALIZATION_FACTOR`.
5. Use that factor only in the gamma path.

Expected behavior:

- `G1` uses `5.5e-7`
- `G2` uses `5.0e-7`
- missing machine mapping should be handled explicitly:
  - either leave normalization unset and continue only if the workflow permits it
  - or fail fast with a clear config/runtime error if product requirements demand strict machine coverage

Recommendation: fail fast for gamma mode when a configured machine-specific mapping is expected but missing, because silent fallback would make validation ambiguous.

### Gamma Report Format

Gamma report output should follow the newer worktree layout:

- one beam summary page per beam
- visual pages grouped in batches of 4 layer figures per PDF page
- each layer figure still contains 3 panels:
  - `Plan Fluence`
  - `Log Fluence`
  - `Gamma Map`

This reduces PDF page count substantially while preserving per-layer visualization.

## Files To Compare And Merge

Primary files in `main` to review and update:

- Modify: `config.yaml`
- Modify: `main.py`
- Modify: `src/config_loader.py`
- Modify: `src/gamma_report_layout.py`
- Modify: `src/gamma_report_generator.py`
- Modify: `src/__init__.py`
- Modify: `tests/test_config_loader.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_gamma_report_generator.py`

Reference files in the worktree containing the desired behavior:

- Reference: `.worktrees/fluence-gamma/config.yaml`
- Reference: `.worktrees/fluence-gamma/main.py`
- Reference: `.worktrees/fluence-gamma/src/config_loader.py`
- Reference: `.worktrees/fluence-gamma/src/gamma_report_layout.py`
- Reference: `.worktrees/fluence-gamma/src/gamma_report_generator.py`
- Reference: `.worktrees/fluence-gamma/tests/test_config_loader.py`
- Reference: `.worktrees/fluence-gamma/tests/test_main.py`
- Reference: `.worktrees/fluence-gamma/tests/test_gamma_report_generator.py`

## Task 1: Align Centralized Config Schema In `main`

**Files:**
- Modify: `config.yaml`
- Modify: `src/config_loader.py`
- Test: `tests/test_config_loader.py`

**Step 1: Write the failing test**

Add or update tests to assert that `parse_yaml_config()` in `main`:

- accepts `app.analysis_mode: gamma`
- parses `gamma.fluence_percent_threshold: 5.0`
- parses `gamma.distance_mm_threshold: 2.0`
- parses `gamma.normalization_factor_by_machine`
- normalizes machine names to uppercase in the parsed map

Example test sketch:

```python
def test_parse_yaml_config_maps_machine_specific_gamma_normalization(self):
    yaml_path = os.path.join(self.test_dir, "config.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("app:\n")
        f.write("  report_style_summary: true\n")
        f.write("  export_pdf_report: false\n")
        f.write("  export_report_csv: false\n")
        f.write("  save_debug_csv: false\n")
        f.write("  analysis_mode: gamma\n")
        f.write("gamma:\n")
        f.write("  fluence_percent_threshold: 5.0\n")
        f.write("  distance_mm_threshold: 2.0\n")
        f.write("  normalization_factor_by_machine:\n")
        f.write("    G1: 5.5e-7\n")
        f.write("    g2: 5.0e-7\n")

    config = parse_yaml_config(yaml_path)

    assert config["GAMMA_FLUENCE_PERCENT_THRESHOLD"] == 5.0
    assert config["GAMMA_DISTANCE_MM_THRESHOLD"] == 2.0
    assert config["GAMMA_NORMALIZATION_FACTOR_BY_MACHINE"] == {
        "G1": 5.5e-7,
        "G2": 5.0e-7,
    }
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_config_loader.py -q
```

Expected: FAIL if `main` does not yet parse the normalization map or the updated threshold value.

**Step 3: Write minimal implementation**

Update `src/config_loader.py` to:

- parse `analysis_mode`
- parse gamma settings including `normalization_factor_by_machine`
- validate gamma booleans/floats
- preserve a parsed `GAMMA_NORMALIZATION_FACTOR_BY_MACHINE` dict for runtime selection

Update `config.yaml` default gamma thresholds to:

- `fluence_percent_threshold: 5.0`
- `distance_mm_threshold: 2.0`

**Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_config_loader.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add config.yaml src/config_loader.py tests/test_config_loader.py
git commit -m "feat: add centralized gamma config schema"
```

## Task 2: Merge Runtime Machine-Specific Normalization Into `main`

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

Add a test asserting that when `machine_name == "G2"` and the parsed config contains:

```python
{"GAMMA_NORMALIZATION_FACTOR_BY_MACHINE": {"G1": 5.5e-7, "G2": 5.0e-7}}
```

the config passed to `calculate_gamma_for_layer()` includes:

```python
{"GAMMA_NORMALIZATION_FACTOR": 5.0e-7}
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_main.py -q
```

Expected: FAIL if `main.py` does not yet resolve the machine-specific factor before gamma calculation.

**Step 3: Write minimal implementation**

Add a helper to `main.py`, similar to the worktree version:

```python
def _resolve_machine_gamma_config(app_config, machine_name):
    analysis_config = dict(app_config)
    normalization_map = analysis_config.get("GAMMA_NORMALIZATION_FACTOR_BY_MACHINE", {})
    normalization_factor = normalization_map.get(str(machine_name).upper())
    if normalization_factor is not None:
        analysis_config["GAMMA_NORMALIZATION_FACTOR"] = float(normalization_factor)
    return analysis_config
```

Then merge config with:

```python
analysis_config = {**machine_config, **_resolve_machine_gamma_config(app_config, machine_name)}
```

**Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_main.py -q
```

Expected: PASS for the new gamma-normalization routing test.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: resolve gamma normalization by machine"
```

## Task 3: Merge The Revised Gamma PDF Layout Into `main`

**Files:**
- Modify: `src/gamma_report_layout.py`
- Modify: `src/gamma_report_generator.py`
- Test: `tests/test_gamma_report_generator.py`

**Step 1: Write the failing test**

Add or update tests asserting:

- `_generate_gamma_visual_page()` accepts a batch of up to 4 layers
- one visual page contains 4 layer figures, each with 3 panels
- `generate_gamma_report()` batches layers 4 per visual page instead of 1 per page

Example expectation:

- 5 layer entries should produce 2 visual pages for that beam

**Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_gamma_report_generator.py -q
```

Expected: FAIL if `main` still uses one layer per page.

**Step 3: Write minimal implementation**

Update `src/gamma_report_generator.py` to batch layers in groups of 4.

Update `src/gamma_report_layout.py` so `generate_gamma_visual_page()` renders:

- a 4x3 axis grid
- one row per layer figure
- three columns per row:
  - `Plan Fluence`
  - `Log Fluence`
  - `Gamma Map`

Hide unused rows when the final batch contains fewer than 4 layers.

**Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_gamma_report_generator.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/gamma_report_layout.py src/gamma_report_generator.py tests/test_gamma_report_generator.py
git commit -m "feat: batch gamma report visuals four per page"
```

## Task 4: Validate Config-Driven Mode Routing In `main`

**Files:**
- Modify: `tests/test_main.py`
- Modify: `main.py` only if needed

**Step 1: Write the failing test**

Ensure `tests/test_main.py` covers both centralized config modes:

- `analysis_mode: trajectory` routes to trajectory calculator/reporting
- `analysis_mode: gamma` routes to gamma calculator/reporting

Important: keep the routing tests explicit so future changes do not accidentally tie mode switching to CLI or implicit defaults.

**Step 2: Run test to verify it fails if behavior regresses**

Run:

```bash
python -m pytest tests/test_main.py -q
```

Expected: either existing gamma-routing tests already pass or new mode-specific assertions fail until completed.

**Step 3: Write minimal implementation**

Only adjust `main.py` if the current config-driven routing is incomplete or inconsistent with the merged worktree behavior.

**Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_main.py -q
```

Expected: PASS for both trajectory and gamma routing tests.

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "test: cover config-driven analysis mode routing"
```

## Task 5: End-To-End Validation On G1 And G2 Using Centralized Config

**Files:**
- Modify: `config.yaml` as needed for validation runs
- Generate output under `output/55758663_gamma_main` and `output/55061194_gamma_main`

**Step 1: Run G1 in gamma mode**

Set centralized config to gamma mode and run:

```bash
python main.py \
  --log_dir /home/jokh38/MOQUI_SMC/data/SHI_log/55758663 \
  --dcm_file /home/jokh38/MOQUI_SMC/data/SHI_log/55758663/RP.1.2.840.113854.116162735116359465886295179291233309871.1.dcm \
  --output /home/jokh38/MOQUI_SMC/ptn_checker/output/55758663_gamma_main
```

Expected:

- machine detected as `G1`
- `5.5e-7` normalization selected
- gamma PDF produced

**Step 2: Run G2 in gamma mode**

```bash
python main.py \
  --log_dir /home/jokh38/MOQUI_SMC/data/SHI_log/55061194 \
  --dcm_file /home/jokh38/MOQUI_SMC/data/SHI_log/55061194/RP.1.2.840.113854.241506614174277151614979936366782948539.1.dcm \
  --output /home/jokh38/MOQUI_SMC/ptn_checker/output/55061194_gamma_main
```

Expected:

- machine detected as `G2`
- `5.0e-7` normalization selected
- gamma PDF produced

**Step 3: Inspect generated PDFs**

Run:

```bash
pdfinfo /home/jokh38/MOQUI_SMC/ptn_checker/output/55758663_gamma_main/55758663_$(date +%F).pdf
pdfinfo /home/jokh38/MOQUI_SMC/ptn_checker/output/55061194_gamma_main/55061194_$(date +%F).pdf
```

Expected:

- valid PDF files
- page counts consistent with 4 layer figures per visual page rather than 1 layer per page

**Step 4: Focused component verification**

Run:

```bash
python -m pytest tests/test_config_loader.py tests/test_main.py tests/test_gamma_workflow.py tests/test_gamma_analysis.py tests/test_fluence_map.py tests/test_gamma_report_generator.py -q
```

Expected: PASS.

**Step 5: Record validation status explicitly**

Document results as:

- `component validated` for the focused pytest suite
- `end-to-end validated` only after both G1 and G2 centralized-config runs succeed and produce PDFs

**Step 6: Commit**

```bash
git add config.yaml output/55758663_gamma_main output/55061194_gamma_main
git commit -m "feat: integrate centralized gamma analysis into main"
```

## Reporting Requirements For The Final Implementation

The final implementation report should separate:

- **Observations**
  - what was changed in `main`
  - which tests passed
  - which sample datasets were run
  - generated output paths
- **Assumptions**
  - any assumptions about missing machine mappings
  - any assumptions about CSV behavior in gamma mode
- **Known gaps**
  - unsupported gamma CSV export, if still intentionally omitted
  - any residual difference between worktree and `main`

Do not claim end-to-end success from tests alone.

