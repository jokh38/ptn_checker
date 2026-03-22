# Implementation Plan: Low-MU Spot Suppression Filter

## Overview

Add an optional per-layer filter that excludes log samples assigned to spots whose plan MU is below a configurable threshold. This filter is combined with the existing zero-dose filter mask, so either filter can be enabled independently or both can run together.

The implementation must preserve a clear distinction between:
- raw statistics
- filtered statistics
- filtered mode requested but no filtered statistics available

That distinction already matters for report generation. Missing `filtered_*` keys cannot be treated as equivalent to zero-valued filtered metrics.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Filter type | Binary threshold | The goal is to suppress low-MU spots, not reweight them |
| MU source | Plan MU for the assigned spot | Reflects planned delivery intent |
| Coexistence | Combined with zero-dose filtering via logical AND | Matches the current mask-based pipeline |
| Independent toggle | `low_mu_filter.enabled` | Allows low-MU-only, zero-dose-only, both, or neither |
| Empty filtered set | Keep raw stats intact and mark filtered stats unavailable | Prevents falsely showing zero-valued filtered metrics |
| Scope | Per-layer only | Consistent with current result structure |

## Required Behavior

1. `filtered_mask` starts from `settled_mask`.
2. Zero-dose exclusions are applied only when `ZERO_DOSE_FILTER_ENABLED` is true.
3. Low-MU exclusions are applied only when `LOW_MU_FILTER_ENABLED` is true.
4. When any filter is active but `filtered_mask` contains no included samples, the layer must record that filtered metrics are unavailable.
5. The report layer must not silently substitute zeros for unavailable filtered metrics.

## File Changes

### 1. `config.yaml`

Add a new top-level section after `zero_dose_filter`:

```yaml
low_mu_filter:
  enabled: false
  min_mu: 0.01              # spots with plan MU below this value are excluded
```

Notes:
- `enabled: false` keeps the feature opt-in.
- `min_mu` is expressed in MU units.
- Samples assigned to spots with `assigned_spot_mu < min_mu` are excluded from filtered statistics.

---

### 2. `src/config_loader.py`

Add parsing and validation for `low_mu_filter`.

#### 2a. Add defaults near `DEFAULT_ZERO_DOSE_FILTER`

```python
DEFAULT_LOW_MU_FILTER = {
    "enabled": False,
    "min_mu": 0.01,
}
```

#### 2b. Add a parser after `_parse_zero_dose_filter_config()`

Do not reuse the current `bool(...)` coercion pattern for booleans. YAML strings such as `"false"` become truthy under `bool("false")`, which is incorrect.

Recommended parser shape:

```python
def _parse_low_mu_filter_config(yaml_data: dict) -> dict:
    section = yaml_data.get("low_mu_filter") or {}
    if not isinstance(section, dict):
        raise ValueError("Invalid YAML structure: 'low_mu_filter' must be a dict")

    merged = DEFAULT_LOW_MU_FILTER.copy()
    merged.update(section)

    enabled = merged["enabled"]
    if not isinstance(enabled, bool):
        raise ValueError("low_mu_filter.enabled must be a boolean")

    return {
        "LOW_MU_FILTER_ENABLED": enabled,
        "LOW_MU_FILTER_MIN_MU": float(merged["min_mu"]),
    }
```

#### 2c. Extend `_validate_app_config()`

Add:

```python
    if config.get("LOW_MU_FILTER_MIN_MU", 0) < 0:
        raise ValueError("LOW_MU_FILTER_MIN_MU must be >= 0")
```

#### 2d. Integrate into `parse_yaml_config()`

Add:

```python
    config.update(_parse_low_mu_filter_config(yaml_data))
```

after:

```python
    config.update(_parse_zero_dose_filter_config(yaml_data))
```

---

### 3. `src/calculator.py`

All changes are within `calculate_differences_for_layer()`.

#### 3a. Build the low-MU mask

Insert after the boundary-carryover logic and before `zero_dose_filter_enabled` is read:

```python
    low_mu_filter_enabled = bool(config.get("LOW_MU_FILTER_ENABLED", False))
    low_mu_min_mu = float(config.get("LOW_MU_FILTER_MIN_MU", 0.01))
    sample_is_below_mu_threshold = np.zeros(len(diff_x), dtype=bool)
    if low_mu_filter_enabled:
        sample_is_below_mu_threshold = spot_mu[assigned_spot_index] < low_mu_min_mu
```

#### 3b. Build a combined `filtered_mask`

Replace the current unconditional zero-dose-shaped mask construction with:

```python
    zero_dose_filter_enabled = bool(config.get("ZERO_DOSE_FILTER_ENABLED", False))
    filtered_mask = settled_mask.copy()
    if zero_dose_filter_enabled:
        filtered_mask &= ~sample_is_transit_min_dose
        filtered_mask &= ~sample_is_boundary_carryover
    if low_mu_filter_enabled:
        filtered_mask &= ~sample_is_below_mu_threshold

    any_filter_active = zero_dose_filter_enabled or low_mu_filter_enabled
    sample_is_included_filtered_stats = (
        filtered_mask if any_filter_active else settled_mask.copy()
    )
```

This avoids computing a zero-dose-style exclusion mask when zero-dose filtering is disabled.

#### 3c. Replace fallback-to-raw statistics with explicit availability state

Do not use `_calculate_stats_with_fallback()` for filtered statistics once low-MU filtering is added.

Use:

```python
    filtered_stats_x = filtered_stats_y = None
    filtered_diff_x = filtered_diff_y = None
    filtered_stats_available = False
    if any_filter_active:
        included_diff_x = diff_x[filtered_mask]
        included_diff_y = diff_y[filtered_mask]
        if included_diff_x.size > 0 and included_diff_y.size > 0:
            filtered_stats_x = _calculate_axis_stats(included_diff_x)
            filtered_stats_y = _calculate_axis_stats(included_diff_y)
            filtered_diff_x = included_diff_x
            filtered_diff_y = included_diff_y
            filtered_stats_available = True
```

Also store an explicit result flag:

```python
    results["filtered_stats_available"] = filtered_stats_available
```

If `_calculate_stats_with_fallback()` is no longer used anywhere else, remove the helper and its legacy `filtered_stats_fallback_to_raw` output.

#### 3d. Store the new mask in results

Add:

```python
    results["sample_is_below_mu_threshold"] = sample_is_below_mu_threshold
```

alongside the existing mask outputs.

#### 3e. Write filtered result keys only when filtered stats are available

Update the filtered-results block to use:

```python
    if any_filter_active and filtered_stats_available:
```

and do not write `filtered_stats_fallback_to_raw`.

Keep these counters written whenever `any_filter_active`, even if no filtered stats are available:
- `num_filtered_samples`
- `num_included_samples`
- `filtered_sample_fraction`
- `filtered_mu_fraction_estimate`

That gives downstream code visibility into why filtered metrics are missing.

#### 3f. Add the new mask to the debug CSV

Add:

```python
            sample_is_below_mu_threshold.astype(int),
```

between `sample_is_boundary_carryover` and `sample_is_included_filtered_stats`, and add the matching CSV header column:

```text
sample_is_below_mu_threshold
```

---

### 4. `src/report_generator.py`

Report changes are required. They are not optional.

#### 4a. Fix metric selection for unavailable filtered stats

The current `_metric_key()` / `_metric_value()` logic falls back to raw keys only when `filtered_*` keys are absent, and otherwise returns `0` if the selected key is missing. That is not sufficient once filtered mode can legitimately produce an empty filtered set.

Update the metric-selection logic so that:
- if `report_mode == "raw"`, raw metrics are used
- if `report_mode != "raw"` and filtered stats are available, filtered metrics are used
- if `report_mode != "raw"` and filtered stats are unavailable, the report explicitly falls back to raw metrics or displays an explicit unavailable state, according to the chosen UX

Recommended minimal approach:
- use `results.get("filtered_stats_available", False)` as the gate
- when filtered stats are unavailable, fall back to raw metrics rather than returning `0`

This preserves stable report output and avoids false passes caused by zero-valued placeholders.

#### 4b. Fix the filter-status label

The current label text says:

```text
Zero-dose filter active: {report_mode} metrics shown
```

That becomes incorrect when:
- only low-MU filtering is enabled
- both filters are enabled
- filtered mode is requested but filtered stats are unavailable and raw metrics are shown

Update the report input or render logic so the label reflects the actual state, for example:
- `Filtered metrics shown`
- `Filtered metrics unavailable for some layers; raw metrics shown`
- `Zero-dose + low-MU filtering active`
- `Low-MU filtering active`

The exact wording can be compact, but the label must not claim zero-dose filtering when only low-MU filtering is active.

---

## Summary of Changes by File

| File | Nature |
|------|--------|
| `config.yaml` | New `low_mu_filter` section |
| `src/config_loader.py` | New parser and validation, with strict boolean handling |
| `src/calculator.py` | Low-MU mask, combined filtering, explicit filtered-stats availability state, CSV column |
| `src/report_generator.py` | Correct metric fallback behavior and accurate filter-status labeling |

## Data Flow After Changes

```text
calculate_differences_for_layer()
  |
  +-- settled_mask
  +-- sample_is_transit_min_dose
  +-- sample_is_boundary_carryover
  +-- sample_is_below_mu_threshold
  |
  +-- filtered_mask = settled_mask
  |     & (~transit)   when ZERO_DOSE_FILTER_ENABLED
  |     & (~boundary)  when ZERO_DOSE_FILTER_ENABLED
  |     & (~below_mu)  when LOW_MU_FILTER_ENABLED
  |
  +-- any_filter_active = ZERO_DOSE_FILTER_ENABLED or LOW_MU_FILTER_ENABLED
  +-- filtered_stats_available = any_filter_active and filtered_mask has included samples
  |
  +-- if filtered_stats_available:
  |       write filtered_* metrics
  |
  +-- always write raw metrics
  +-- always write mask/counter fields
```

## Filter Interaction Matrix

| Zero-Dose Filter | Low-MU Filter | `filtered_mask` includes |
|:-:|:-:|---|
| off | off | `settled_mask` only |
| on | off | settled & not transit & not boundary |
| off | on | settled & not below-mu-threshold |
| on | on | settled & not transit & not boundary & not below-mu-threshold |

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `min_mu = 0` | No samples excluded by low-MU filtering |
| All settled samples excluded by active filters | `filtered_stats_available = False`; raw stats remain present; report must not substitute zeros |
| `low_mu_filter.enabled = false` | `sample_is_below_mu_threshold` stays all-False |
| Zero-dose already excludes a spot | Low-MU filtering may be redundant for that spot; combined mask remains correct |
| Spot with `plan_mu = 0` | Excluded by low-MU filtering when `min_mu > 0`; may also be excluded by zero-dose filtering |

## Test Plan

Use `python -m pytest`, not bare `pytest`.

### Test 1: Low-MU filter excludes samples below threshold

Create a layer with spot MU values `[0.1, 0.005, 0.05, 0.002]` and set `min_mu = 0.01`. Verify:
- `sample_is_below_mu_threshold` is true for the `0.005` and `0.002` spots
- `sample_is_included_filtered_stats` excludes those samples
- filtered statistics are computed from only the remaining included samples

### Test 2: Low-MU and zero-dose filters coexist

Enable both filters. Verify:
- transit or boundary-carryover samples are excluded by zero-dose filtering
- low-MU treatment samples are excluded by low-MU filtering
- `filtered_mask` reflects both exclusion classes

### Test 3: Active filters exclude all settled samples

Set `min_mu` above every spot MU value for a test layer. Verify:
- `filtered_stats_available` is false
- no `filtered_mean_diff_x` key is written
- raw metrics remain present
- the report path does not render zeros as filtered metrics

### Test 4: Low-MU filter disabled has no effect

Set `LOW_MU_FILTER_ENABLED = False`. Verify:
- `sample_is_below_mu_threshold` is all-False
- `filtered_mask` matches the zero-dose-only baseline

### Test 5: Debug CSV includes the new column

Enable debug CSV output. Verify:
- `sample_is_below_mu_threshold` is present in the header
- values are `0` or `1` and match expected spot assignments

### Test 6: Config validation

Verify:
- `min_mu: -1` raises `ValueError`
- missing `low_mu_filter` uses defaults
- non-dict `low_mu_filter` raises `ValueError`
- non-boolean `low_mu_filter.enabled` raises `ValueError`

### Test 7: Report behavior with unavailable filtered stats

In filtered report mode with `filtered_stats_available = False`, verify:
- the report does not show zero-valued filtered metrics unless the true metric is zero
- the label reflects the actual filter state and fallback behavior

## Notes

- This plan is component-scoped. It does not claim end-to-end validated behavior.
- Any implementation report should explicitly label results as `component validated` or `end-to-end validated`.
