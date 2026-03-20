# Feature: Add Velocity and MU Values to Debug CSV

## Request

Add velocity and MU values for plan/log at each debug CSV sample row.

## Current State

### CSV Output

- **File**: `src/calculator.py:143-158`
- **Trigger**: `SAVE_DEBUG_CSV=on` in config.yaml
- **Scope**: First processed layer only (`debug_csv_saved` flag in `main.py:90,124,140`)

### Current Columns

```
log_time_s, interp_plan_x, interp_plan_y, log_x, log_y, x_raw, y_raw, layer_num, beam_on_off, is_settling
```

## Available Data

### Plan Side (`plan_layer` dict, built in `dicom_parser.py:136-147`)

| Key | Shape | Description |
|-----|-------|-------------|
| `cumulative_mu` | (n_spots,) | `np.cumsum(mus_array)`, cumulative MU per spot |
| `time_axis_s` | (n_spots,) | Time at each spot (from `plan_timing.py:92-94`) |
| `trajectory_x_mm` | (n_spots,) | Spot x-positions in mm |
| `trajectory_y_mm` | (n_spots,) | Spot y-positions in mm |
| `segment_times_s` | (n_spots,) | Time per segment (0-padded at front) |

`cumulative_mu` and `time_axis_s` share the same length (both indexed per spot), so `np.interp(log_time_s, plan_time_s, plan_cumulative_mu)` works directly.

### Log Side (`log_data` dict, built in `log_parser.py`)

| Key | Shape | Description |
|-----|-------|-------------|
| `mu` | (n_samples,) | Cumulative MU from `np.cumsum(filtered_dose1)` (`log_parser.py:245`) |
| `time_ms` | (n_samples,) | Log timestamps in ms |
| `x` | (n_samples,) | Calibrated x-position in mm |
| `y` | (n_samples,) | Calibrated y-position in mm |

Note: `log_data['mu']` may have MU correction applied upstream via `apply_mu_correction()` in `main.py:115-117` when a PlanRange entry is available.

## New Columns

### Velocity (scanning velocity, mm/s)

Computed from log positions (the measured beam path):

```
dx = log_x[i] - log_x[i-1]
dy = log_y[i] - log_y[i-1]
dt = log_time_s[i] - log_time_s[i-1]
velocity[i] = sqrt(dx**2 + dy**2) / dt
```

Edge cases:
- `velocity[0] = 0.0` (no previous point)
- If `dt == 0`: `velocity[i] = 0.0` (guard against division by zero)

### MU (both plan and log, for comparison)

- **`interp_plan_mu`**: Plan cumulative MU interpolated to log time via `np.interp(log_time_s, plan_time_s, plan_cumulative_mu)`
- **`log_mu`**: `log_data['mu']` (already at log sample rate)

### Updated Column List

```
log_time_s, interp_plan_x, interp_plan_y, log_x, log_y, x_raw, y_raw,
layer_num, beam_on_off, is_settling, log_velocity_mm_s, interp_plan_mu, log_mu
```

## Scope Change: All Layers

Currently only the first layer gets a CSV. To emit CSVs for all layers:

- Remove the `debug_csv_saved` flag gating in `main.py:90,124,140`
- Keep `save_debug_csv` config check
- Each layer already gets a unique filename via `debug_data_beam_{beam_number}_layer_{layer_index}.csv` (`main.py:128-130`)

## Implementation Steps

### Step 1: Remove first-layer-only restriction (`main.py`)

Delete `debug_csv_saved` flag and simplify the gating:

```python
# Before (main.py:124)
save_csv_for_this_layer = save_debug_csv and not debug_csv_saved

# After
save_csv_for_this_layer = save_debug_csv
```

Remove lines 90 (`debug_csv_saved = False`) and 139-140 (`if save_csv_for_this_layer: debug_csv_saved = True`).

### Step 2: Use existing MU data already available in `calculate_differences_for_layer` (`calculator.py`)

In `calculate_differences_for_layer`, after the existing interpolation of plan positions (`calculator.py:99-106`):

1. Extract `plan_layer['cumulative_mu']` (with fallback if absent).
2. Interpolate to log time: `interp_plan_mu = np.interp(log_time_s, plan_time_s, plan_cumulative_mu)`.
3. Extract `log_data['mu']` (with fallback if absent).

No change is needed in `main.py` for argument passing: it already passes the full `layer_data` / `plan_layer` dict into `calculate_differences_for_layer(...)`.

### Step 3: Compute velocity (`calculator.py`)

After position data is prepared:

```python
dx = np.diff(log_x, prepend=log_x[0])
dy = np.diff(log_y, prepend=log_y[0])
dt = np.diff(log_time_s, prepend=log_time_s[0])
speed = np.zeros_like(dt)
nonzero = dt > 0
speed[nonzero] = np.sqrt(dx[nonzero]**2 + dy[nonzero]**2) / dt[nonzero]
```

### Step 4: Add new columns to CSV output (`calculator.py:145-158`)

Extend `np.column_stack` and header string with the three new columns.

### Step 5: Update tests (`tests/test_calculator.py`)

- Existing CSV test (`test_calculator_writes_settling_flag_to_csv`, line ~163) must add `cumulative_mu` to `plan_layer` and `mu` to `log_data` fixtures.
- Add a test that verifies the three new columns appear in the CSV header and have correct values for a simple known-geometry case.

## Risks

- **Backward compatibility**: External tools parsing the CSV by column index will break. Column-name-based parsing is unaffected. This is acceptable for a debug output.
- **Performance**: Negligible; three extra arrays in `np.column_stack` per layer.
- **Missing keys**: If `cumulative_mu` or `mu` are absent (old data formats), fill with zeros and log a warning rather than failing.
