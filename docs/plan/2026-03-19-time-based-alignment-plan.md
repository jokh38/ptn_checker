# Time-Based Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace MU-based plan/log alignment with time-based alignment as the default and only comparison method in the codebase.

**Architecture:** Move timing reconstruction to the plan-parsing side so each parsed layer carries a reusable time-domain trajectory derived from DICOM spot positions, per-spot MU, beam energy, and `LS_doserate.csv`. Then rewrite the calculator to align plan and PTN data by rebased log time instead of cumulative MU, preserving the existing report/statistics outputs.

**Tech Stack:** Python, NumPy, SciPy, pydicom, pytest

---

### Design Decisions (must be resolved before implementation)

#### D1: Unit convention — all internal positions are in cm

`Dicom_reader_F.py` (the reference implementation) works in **cm**: it applies a `0.1*` factor when reading DICOM positions (`positions = np.reshape(0.1*t1, ...)`), and its constants are cm-based (`MAX_SPEED = 2000 cm/s`). The existing `src/dicom_parser.py` stores positions in **mm** (decoded via `F_SHI_spotP`).

**Resolution:** `src/plan_timing.py` will work in **cm** internally, matching `Dicom_reader_F.py`. The `dicom_parser.py` integration (Task 2) must convert mm positions to cm before calling `build_layer_time_trajectory`:

```python
positions_cm = plan_layer['positions'] * 0.1  # mm -> cm
```

The trajectory output arrays (`trajectory_x_mm`, `trajectory_y_mm`) will be converted **back to mm** before storage on the layer dict, so the calculator and reports continue to work in mm. Constants in `plan_timing.py`: `MAX_SPEED = 2000` (cm/s), `MIN_DOSERATE = 1.4` (MU/s).

#### D2: `LS_doserate.csv` is MATLAB format, not CSV

The file uses MATLAB syntax:
```
LS_doserate = ...
  [230 20;
   229.6 20;
```

It is **not** comma-delimited. `Dicom_reader_F.py` calls `np.loadtxt(delimiter=',')` which would fail on this format.

**Resolution:** `get_doserate_for_energy` must parse the actual file format:
1. Strip the header line (`LS_doserate = ...`)
2. Remove bracket characters (`[`, `]`) and semicolons (`;`)
3. Parse remaining whitespace-delimited numeric pairs (energy, doserate)
4. Alternatively, convert the file to proper CSV as a prerequisite step and update the reference in code

The implementer should verify which approach is simpler and add a test that loads the real `LS_doserate.csv` file.

#### D3: Line scanning uses continuous-motion delivery, not hold-then-transit

In line scanning (as implemented in `Dicom_reader_F.py` `Layer.calculate_scan_times`), the beam delivers dose **while moving** between consecutive positions. There is no stationary hold phase at each spot. The correct model:

- **Segment[0]**: starting position only (distance = 0, contributes no scan time)
- **Segment[i] (i >= 1)**: beam moves from position[i-1] to position[i]
  - If `weight[i] >= 1e-7`: scan time = `weight[i] / layer_doserate` (delivery during motion)
  - If `weight[i] < 1e-7`: scan time = `distance[i] / MAX_SPEED` (pure transit, no delivery)
- Position at any time within a segment is **linearly interpolated** between start and end positions over that segment's scan time

The trajectory arrays should have one time point per position (cumulative scan time at each position), with linear interpolation assumed between them.

#### D4: Plan-vs-log time range mismatch

Reconstructed plan time and actual log time will differ in total duration. When `np.interp` extrapolates beyond the plan's time range, it clamps to the last plan position, hiding real deviations.

**Resolution:** After interpolation, compute the fraction of log samples that fall outside the plan time range. If > 5%, log a warning. Report the overlap ratio in the layer results dict as `time_overlap_fraction` so it appears in debug output. Do **not** normalize both to [0, 1] (that would replicate the MU-norm approach).

#### D5: Test infrastructure must be updated

The existing `tests/conftest.py` `create_dummy_dcm_file` helper does not set `NominalBeamEnergy` on control points. After Task 2, the parser will call `build_layer_time_trajectory` which requires energy and a working doserate lookup.

**Resolution:** Update `conftest.py` in Task 2 to:
- Set `NominalBeamEnergy` on dummy control points (e.g., 150.0 MeV)
- Ensure the dummy energy has a matching entry in `LS_doserate.csv`, or mock the doserate lookup in tests

#### D6: Post-implementation MU normalization study

Follow-up analysis on March 20, 2026 checked whether the corrected PTN cumulative MU could be compared directly against RTPLAN MU on a per-layer basis. The tested normalization value was:

```python
alpha_layer = plan_layer_total_mu / corrected_log_layer_total_mu
```

where `plan_layer_total_mu = sum(plan_layer["mu"])` and `corrected_log_layer_total_mu = log_data["mu"][-1]` after `apply_mu_correction()`.

**Observation:** raw corrected PTN MU and RTPLAN MU are not numerically interchangeable. They differ by a large machine-stable scale factor, so direct MU-axis interpolation without per-layer normalization is not defensible.

**Component-validated data points**

- G2 case root: `/home/jokh38/MOQUI_SMC/data/SHI_log/55061194`
- G1 case root: `/home/jokh38/MOQUI_SMC/data/SHI_log/55758663`
- Verification scripts used `parse_dcm_file`, `parse_ptn_file`, `parse_planrange_for_directory`, and `apply_mu_correction`

**Machine-level summary**

| Machine | Layers sampled | `alpha = plan/log` mean | std | min | max |
|---------|----------------|-------------------------|-----|-----|-----|
| G2 | 108 | `1.629145e-07` | `2.872131e-08` | `1.103437e-07` | `2.153610e-07` |
| G1 | 108 | `1.507917e-07` | `2.051463e-08` | `1.157870e-07` | `2.207164e-07` |

Equivalent inverse scale:

```python
beta_layer = corrected_log_layer_total_mu / plan_layer_total_mu
```

| Machine | `beta = log/plan` mean | std |
|---------|------------------------|-----|
| G2 | `6.337507e+06` | `1.148393e+06` |
| G1 | `6.752353e+06` | `8.982996e+05` |

**Beam-level summary**

| Machine | Beam | Layers sampled | `alpha` mean | `alpha` std |
|---------|------|----------------|--------------|-------------|
| G2 | `1G180:TX` | 34 | `1.670465e-07` | `2.685477e-08` |
| G2 | `2G225:TX` | 32 | `1.690517e-07` | `2.556830e-08` |
| G2 | `3G140:TX` | 42 | `1.548936e-07` | `3.053615e-08` |
| G1 | `1G000:TX` | 35 | `1.564808e-07` | `1.864278e-08` |
| G1 | `2G010:TX` | 34 | `1.501882e-07` | `1.716118e-08` |
| G1 | `3G310:TX` | 39 | `1.462123e-07` | `2.337607e-08` |

**Mapping note**

- G2 delivery directories map directly by `PlanRange.txt` `FLD_NO` to RTPLAN treatment beam numbers `2`, `3`, and `4`.
- G1 delivery directories use `FLD_NO` values `5`, `6`, and `7`, while the RTPLAN treatment beams are numbered `2`, `3`, and `4`.
- For G1, the mapping was resolved by ordered delivered field to ordered non-setup beam, cross-checked by identical layer counts:
  - field `5` -> beam `2` (`1G000:TX`, 35 layers)
  - field `6` -> beam `3` (`2G010:TX`, 34 layers)
  - field `7` -> beam `4` (`3G310:TX`, 39 layers)

**Resolution:** keep time-based alignment as the production comparison basis. If a future MU-basis analysis is added, it must use a normalized per-layer MU coordinate such as:

```python
u_plan = plan_layer["cumulative_mu"] / plan_layer["cumulative_mu"][-1]
u_log = log_data["mu"] / log_data["mu"][-1]
```

and it should treat each planned spot as a MU interval, not as a single MU endpoint. This preserves comparability despite the machine-dependent scale mismatch between corrected PTN MU and RTPLAN MU.

---

### Task 1: Add focused timing tests for plan-side reconstruction

**Files:**
- Create: `tests/test_plan_timing.py`
- Create: `src/plan_timing.py`
- Reference: `Dicom_reader_F.py` (lines 102-164: `Layer.calculate_scan_times`)
- Reference: `LS_doserate.csv`

**Unit convention:** All positions passed to `build_layer_time_trajectory` are in **cm**. `MAX_SPEED = 2000 cm/s`. The caller (Task 2) is responsible for mm-to-cm conversion before calling.

**Step 1: Write the failing tests**

```python
import numpy as np

from src.plan_timing import (
    build_layer_time_trajectory,
    get_doserate_for_energy,
    load_doserate_table,
)


def test_load_doserate_table_parses_matlab_format():
    """LS_doserate.csv uses MATLAB syntax, not standard CSV."""
    table = load_doserate_table()
    assert table.shape[1] == 2  # (energy, doserate) columns
    assert table.shape[0] > 0
    assert table[0, 0] == 230.0  # first energy entry


def test_get_doserate_for_energy_returns_table_value():
    """Energy window: [energy, energy+0.3) matching Dicom_reader_F.py."""
    value = get_doserate_for_energy(150.0)
    assert value > 0


def test_get_doserate_for_energy_returns_zero_for_missing():
    value = get_doserate_for_energy(9999.0)
    assert value == 0


def test_build_layer_time_trajectory_continuous_motion():
    """Line scanning: delivery happens during transit, no hold phase.
    Segment[0] is starting position (no time). Segments 1..N carry
    scan time = weight/doserate for delivery or distance/MAX_SPEED for transit.
    """
    # 3 positions in cm: (0,0) -> (10,0) -> (10,20)
    positions_cm = np.array([
        [0.0, 0.0],
        [10.0, 0.0],
        [10.0, 20.0],
    ])
    mu = np.array([1.0, 2.0, 0.0])

    trajectory = build_layer_time_trajectory(
        positions_cm=positions_cm,
        mu=mu,
        energy=150.0,
    )

    # Time axis starts at 0 (position[0]) and has one entry per position
    assert trajectory["time_axis_s"][0] == 0.0
    assert len(trajectory["time_axis_s"]) == 3
    assert trajectory["layer_doserate_mu_per_s"] >= 1.4
    assert len(trajectory["time_axis_s"]) == len(trajectory["x_cm"])
    assert len(trajectory["time_axis_s"]) == len(trajectory["y_cm"])
    assert trajectory["total_time_s"] > 0.0

    # Position values match input at trajectory waypoints
    np.testing.assert_array_equal(trajectory["x_cm"], positions_cm[:, 0])
    np.testing.assert_array_equal(trajectory["y_cm"], positions_cm[:, 1])


def test_zero_mu_segment_uses_max_speed_transit_time():
    """Zero-weight segment: pure transit at MAX_SPEED = 2000 cm/s."""
    positions_cm = np.array([
        [0.0, 0.0],
        [20.0, 0.0],  # 20 cm away
    ])
    mu = np.array([0.0, 0.0])

    trajectory = build_layer_time_trajectory(
        positions_cm=positions_cm,
        mu=mu,
        energy=150.0,
    )

    # distance = 20 cm, MAX_SPEED = 2000 cm/s -> time = 0.01 s
    assert np.isclose(trajectory["total_time_s"], 20.0 / 2000.0)
```

**Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_plan_timing.py -v`
Expected: FAIL because `src.plan_timing` does not exist yet.

**Step 3: Write minimal implementation**

Create `src/plan_timing.py` with:
- constants: `MIN_DOSERATE = 1.4` (MU/s), `MAX_SPEED = 2000` (cm/s), `DOSERATE_TABLE_PATH = 'LS_doserate.csv'`
- `load_doserate_table()` that parses the MATLAB-format `LS_doserate.csv`:
  - skip the header line (`LS_doserate = ...`)
  - strip bracket characters (`[`, `]`) and semicolons (`;`)
  - parse whitespace-delimited numeric pairs into an Nx2 array (energy, doserate)
- `get_doserate_for_energy(energy)` that calls `load_doserate_table()` and matches the `Dicom_reader_F.py` energy-window: `(table[:, 0] >= energy) & (table[:, 0] < energy + 0.3)`, returning the first match's doserate or 0
- `build_layer_time_trajectory(positions_cm, mu, energy)` that implements the **continuous-motion line scanning** model:
  - positions_cm: Nx2 array in **cm**, mu: N-length array of per-spot MU
  - computes distances between consecutive positions: `distances[i] = ||pos[i] - pos[i-1]||` for i >= 1
  - computes `mu_per_dist[i] = mu[i] / distances[i]` for segments with distance > 0
  - determines layer doserate: `clamp(min(MAX_SPEED * mu_per_dist), MIN_DOSERATE, doserate_provider)`
  - computes segment scan times (i >= 1):
    - if `mu[i] >= 1e-7`: `scan_time = mu[i] / layer_doserate` (delivery during motion)
    - if `mu[i] < 1e-7`: `scan_time = distances[i] / MAX_SPEED` (pure transit)
  - builds cumulative time axis: `time_axis_s[0] = 0.0`, `time_axis_s[i] = time_axis_s[i-1] + scan_time[i]`
  - position arrays are the input positions themselves (linear interpolation between waypoints is assumed by the consumer)
  - returns dict: `time_axis_s`, `x_cm`, `y_cm`, `segment_times_s`, `layer_doserate_mu_per_s`, `total_time_s`

**Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_plan_timing.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_plan_timing.py src/plan_timing.py
git commit -m "feat: add plan timing reconstruction with continuous-motion model"
```

### Task 2: Extend DICOM parsing to emit time-domain layer data

**Files:**
- Modify: `src/dicom_parser.py`
- Modify: `tests/test_dicom_parser.py`
- Modify: `tests/conftest.py` (update `create_dummy_dcm_file`)
- Reference: `src/plan_timing.py`

**Step 1: Update test infrastructure**

Update `tests/conftest.py` `create_dummy_dcm_file` to:
- Set `NominalBeamEnergy = 150.0` on the first control point of each pair
- Ensure 150.0 MeV has a matching entry in `LS_doserate.csv`, or alternatively mock `get_doserate_for_energy` in timing tests to return a fixed value (e.g., 20.0 MU/s) so tests don't depend on the doserate file

**Step 2: Write the failing tests**

Add assertions in `tests/test_dicom_parser.py` that each parsed layer now includes:

```python
assert "energy" in layer
assert "time_axis_s" in layer
assert "trajectory_x_mm" in layer
assert "trajectory_y_mm" in layer
assert "layer_doserate_mu_per_s" in layer
assert layer["total_time_s"] > 0.0
assert layer["positions"].shape[0] == layer["mu"].shape[0]
# trajectory arrays have same length as time axis
assert len(layer["time_axis_s"]) == len(layer["trajectory_x_mm"])
assert len(layer["time_axis_s"]) == len(layer["trajectory_y_mm"])
```

**Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_dicom_parser.py -v`
Expected: FAIL because the parser does not yet attach timing metadata.

**Step 4: Write minimal implementation**

Update `src/dicom_parser.py` to:
- extract `cp_start.NominalBeamEnergy`
- convert positions from mm to cm: `positions_cm = positions * 0.1`
- call `build_layer_time_trajectory(positions_cm=positions_cm, mu=mus, energy=energy)`
- convert trajectory positions back to mm for storage: `trajectory_x_mm = trajectory["x_cm"] * 10.0`
- store the returned trajectory fields on each layer dict:
  - `energy`
  - `time_axis_s`
  - `trajectory_x_mm` (in mm, converted from cm output)
  - `trajectory_y_mm` (in mm, converted from cm output)
  - `layer_doserate_mu_per_s`
  - `total_time_s`
  - optional debug arrays such as `segment_times_s`
- keep `positions`, `mu`, and `cumulative_mu` for traceability during transition, but stop relying on `cumulative_mu` downstream

**Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_dicom_parser.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/dicom_parser.py tests/test_dicom_parser.py tests/conftest.py
git commit -m "feat: attach time trajectories to parsed plan layers"
```

### Task 3: Rewrite calculator to compare by rebased log time

**Files:**
- Modify: `src/calculator.py`
- Rewrite: `tests/test_calculator.py` (all existing MU-based tests must be replaced)

**Step 1: Write the failing tests**

Replace **all** MU-based tests in `tests/test_calculator.py` with time-based ones. The existing tests (`test_calculate_differences_smoke`, `test_calculate_differences_keys`, `test_calculate_differences_data_shape`, `test_result_structure`) all rely on `plan_layer['cumulative_mu']` and `log_data['mu']` — they must be fully rewritten, not just patched.

```python
def test_calculator_uses_time_axis_for_plan_sampling():
    plan_layer = {
        "time_axis_s": np.array([0.0, 1.0, 2.0]),
        "trajectory_x_mm": np.array([0.0, 0.0, 10.0]),
        "trajectory_y_mm": np.array([0.0, 0.0, 0.0]),
    }
    log_data = {
        "time_ms": np.array([0.0, 500.0, 1000.0, 1500.0, 2000.0]),
        "x": np.array([0.0, 0.0, 0.0, 5.0, 10.0]),
        "y": np.array([0.0, 0.0, 0.0, 0.0, 0.0]),
    }

    results = calculate_differences_for_layer(plan_layer, log_data)
    assert np.allclose(results["diff_x"], 0.0)
```

Add a guard test:

```python
def test_calculator_errors_when_time_axis_is_missing():
    results = calculate_differences_for_layer({"positions": np.zeros((2, 2))}, {"x": np.array([])})
    assert "error" in results
```

Add result-structure tests equivalent to the removed ones:

```python
def test_calculator_result_keys():
    """Verify all downstream keys are present for the report generator."""
    plan_layer = {
        "time_axis_s": np.array([0.0, 1.0]),
        "trajectory_x_mm": np.array([0.0, 5.0]),
        "trajectory_y_mm": np.array([0.0, 5.0]),
    }
    log_data = {
        "time_ms": np.array([0.0, 500.0, 1000.0]),
        "x": np.array([0.0, 2.5, 5.0]),
        "y": np.array([0.0, 2.5, 5.0]),
    }
    results = calculate_differences_for_layer(plan_layer, log_data)
    for key in ('diff_x', 'diff_y', 'mean_diff_x', 'mean_diff_y',
                'std_diff_x', 'std_diff_y', 'rmse_x', 'rmse_y',
                'max_abs_diff_x', 'max_abs_diff_y', 'p95_abs_diff_x',
                'p95_abs_diff_y', 'plan_positions', 'log_positions',
                'hist_fit_x', 'hist_fit_y'):
        assert key in results, f"Missing key: {key}"
```

**Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_calculator.py -v`
Expected: FAIL because `src/calculator.py` still requires `cumulative_mu` and `log_data["mu"]`.

**Step 3: Write minimal implementation**

Rewrite `src/calculator.py` so `calculate_differences_for_layer(...)`:
- requires `time_axis_s`, `trajectory_x_mm`, `trajectory_y_mm` from plan_layer
- requires `time_ms`, `x`, `y` from log_data
- rebases PTN time to layer start:

```python
log_time_s = (log_data["time_ms"] - log_data["time_ms"][0]) / 1000.0
```

- samples the plan trajectory with:

```python
plan_time_s = plan_layer["time_axis_s"]
interp_plan_x = np.interp(log_time_s, plan_time_s, plan_layer["trajectory_x_mm"])
interp_plan_y = np.interp(log_time_s, plan_time_s, plan_layer["trajectory_y_mm"])
```

- computes time overlap fraction and logs a warning if < 95%:

```python
plan_end = plan_time_s[-1]
log_end = log_time_s[-1]
overlap = min(plan_end, log_end) / max(plan_end, log_end) if max(plan_end, log_end) > 0 else 1.0
if overlap < 0.95:
    logger.warning(f"Plan/log time overlap: {overlap:.1%}")
results['time_overlap_fraction'] = overlap
```

- removes all `plan_mu_norm`, `log_mu_norm`, and cumulative-MU alignment code
- updates CSV debug output headers to use `log_time_s` instead of `log_mu_norm`
- preserves the current diff/statistics/report result keys so downstream report code remains stable

**Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_calculator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/calculator.py tests/test_calculator.py
git commit -m "feat: replace MU alignment with time-based sampling"
```

### Task 4: Remove dead MU-alignment assumptions from the workflow

**Files:**
- Modify: `main.py`
- Modify: `README.md`
- Search: `src/`
- Search: `tests/`

**Step 1: Write the failing checks**

Search for stale MU-alignment wording and keys:

Run: `rg -n "log_mu_norm|plan_mu_norm|cumulative_mu|MU-based|MU interpolation" main.py src tests README.md`
Expected: existing matches that must be removed or narrowed to historical/parser-only contexts.

**Step 2: Write minimal implementation**

Update:
- `main.py` only if error handling or debug CSV naming still assumes MU interpolation
- `README.md` to describe time-based alignment as the default method
- any comments/docstrings/tests that still describe MU-based comparison as the calculator behavior

Do not remove parser-level `mu` storage if it is still needed to construct timing; remove only alignment-specific MU comparison code and wording.

**Step 3: Run the checks again**

Run: `rg -n "log_mu_norm|plan_mu_norm|MU-based|MU interpolation" main.py src tests README.md`
Expected: no matches

**Step 4: Commit**

```bash
git add main.py README.md src tests
git commit -m "refactor: remove MU-based alignment references"
```

### Task 5: Validate component behavior across the test suite

**Files:**
- Test: `tests/test_plan_timing.py`
- Test: `tests/test_dicom_parser.py`
- Test: `tests/test_calculator.py`
- Test: `tests/test_main.py` (likely needs fixes — see note below)
- Test: `tests/test_report_generator.py`

**Note:** `tests/test_main.py` runs a full integration test (`test_run_analysis_integration`) that exercises the entire pipeline. After Tasks 1-3, this test will fail unless:
- `conftest.py` was updated in Task 2 to set `NominalBeamEnergy` on dummy DICOM control points
- The doserate lookup works for the dummy energy, or is mocked
- The dummy PTN data produces valid `time_ms` values

If `test_main.py` fails, fix the test infrastructure here before proceeding.

**Step 1: Run targeted verification**

Run: `python -m pytest tests/test_plan_timing.py tests/test_dicom_parser.py tests/test_calculator.py tests/test_main.py tests/test_report_generator.py -v`
Expected: PASS (fix any failures before proceeding)

**Step 2: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS

**Step 3: Record validation scope**

Document in the implementation summary:
- `component validated` if only pytest/unit coverage was completed
- `end-to-end validated` only if a real DICOM/PTN analysis run was executed successfully

**Step 4: Commit**

```bash
git add tests/test_main.py tests/conftest.py
git commit -m "test: verify time-based alignment migration"
```

### Task 6: Run dataset-level comparison on multiple real layers

**Files:**
- Reference: `Data_ex/`
- Modify if needed: `README.md`

**Note on available data:** `Data_ex/` contains one case (`1.2.840.113854.19.1.19271.1`) with two session subdirectories (`2025042401440800` and `2025042401501400`). These are two delivery sessions of the same plan, not two independent cases. Use both sessions as separate runs. If the plan owner can provide a second independent case, that would strengthen validation.

**Step 1: Execute real analysis runs on available sessions**

Run both sessions from `Data_ex/`:

```bash
python main.py --log_dir Data_ex/1.2.840.113854.19.1.19271.1/2025042401440800 \
    --dcm_file Data_ex/1.2.840.113854.19.1.19271.1/RP.*.dcm \
    -o output_session1

python main.py --log_dir Data_ex/1.2.840.113854.19.1.19271.1/2025042401501400 \
    --dcm_file Data_ex/1.2.840.113854.19.1.19271.1/RP.*.dcm \
    -o output_session2
```

**Step 2: Capture aggregate results**

For each run, record:
- number of layers processed
- any skipped/error layers
- mean/std of `rmse_x`, `rmse_y`
- mean/std of `max_abs_diff_x`, `max_abs_diff_y`
- mean `time_overlap_fraction` across layers (check for systematic time mismatches)

Summarize aggregate metrics across runs, not only the best layer.

**Step 3: Classify validation honestly**

- If only individual layers or report generation were checked: `component validated`
- If complete CLI runs succeeded on real data and produced reports without manual intervention: `end-to-end validated`
- Note: both sessions are from the same patient/plan; this is **not** independent cross-case validation

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: record validation results for time-based alignment"
```
