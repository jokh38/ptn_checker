# Draft: MU-Basis Position Comparison Analysis

## Research Summary

### Intent Classification: RESEARCH → POTENTIAL REFACTORING
User wants to investigate feasibility of comparing plan vs delivered positions using **MU (Monitor Units)** as the alignment basis instead of **time**.

---

## Current State: Time-Based Analysis

### Plan Side (DICOM → Time Trajectory)
**File**: `src/dicom_parser.py:69-148`
- Extracts spot positions and MU weights from RT Plan
- Control points processed in pairs (start/end per layer)
- Per-spot MU: `(weight / total_weight) × (end.CumulativeMetersetWeight - start.CumulativeMetersetWeight)`
- Stores: `positions`, `mu`, `cumulative_mu` per layer

**File**: `src/plan_timing.py:38-103`
- `build_layer_time_trajectory()` reconstructs time-domain trajectory
- Calculates segment times: `max(dose_time, transit_time)`
- `dose_time = segment_mu / layer_doserate`
- Results: `time_axis_s`, `trajectory_x_mm`, `trajectory_y_mm`

### Log Side (PTN Parsing)
**File**: `src/log_parser.py:4-248`
- Parses binary PTN files (8 columns × big-endian u2)
- `time_ms` = row_index × TIMEGAIN (fixed sampling interval)
- `dose1_au` → cumulative MU (after filtering)

**File**: `src/mu_correction.py:107-134`
- Applies physics corrections to convert `dose1_au` → corrected MU:
  ```
  corrected = dose1_au
            × proton_per_dose_factor(energy)
            × dose_per_mu_count_factor(energy)
            × monitor_range_factor(code)
            ÷ dose_dividing_factor
  ```

### Current Comparison (`src/calculator.py:69-216`)
```python
# Interpolate plan positions at LOG TIME points
interp_plan_x = np.interp(log_time_s, plan_time_s, plan_x)
interp_plan_y = np.interp(log_time_s, plan_time_s, plan_y)
diff_x = interp_plan_x - log_x  # Position difference at same TIME
diff_y = interp_plan_y - log_y
```

---

## Proposed: MU-Based Position Comparison

### Available Data Structures (CONFIRMED)

**Plan (per layer)** — `plan_data['beams'][n]['layers'][l]`:
| Field | Type | Description |
|-------|------|-------------|
| `positions` | np.array (n_spots, 2) | (x, y) for each spot — **discrete** |
| `mu` | np.array (n_spots,) | MU per spot — **discrete** |
| `cumulative_mu` | np.array (n_spots,) | Running total MU at each spot |
| `time_axis_s` | np.array (n_spots,) | Reconstructed time (currently used) |

**Log (per layer)** — `log_data` dict:
| Field | Type | Description |
|-------|------|-------------|
| `x`, `y` | np.array (n_samples,) | Position — **continuous** samples |
| `mu` | np.array (n_samples,) | **Corrected cumulative MU** (physics-corrected) |
| `time_ms` | np.array (n_samples,) | Continuous time samples |
| `dose1_au` | np.array (n_samples,) | Raw dose counts (before correction) |

### Key Insight: Both Have Cumulative MU!

The critical observation is that **both data sources have cumulative MU**:
- **Plan**: `cumulative_mu` = sum of spot MU weights up to each spot (discrete)
- **Log**: `mu` = corrected cumulative MU from dose1_au (continuous)

This enables MU-based alignment instead of time-based alignment.

---

## Implementation Approaches

### Option A: Align Log to Plan's MU (Spot-Level Comparison) ⭐ RECOMMENDED

Interpolate log positions at plan's discrete spot MU values:

```python
# Plan: discrete spots with cumulative MU
plan_cumulative_mu = plan_layer['cumulative_mu']  # e.g., [0.5, 1.2, 2.1, 3.5, ...]
plan_x = plan_layer['positions'][:, 0]
plan_y = plan_layer['positions'][:, 1]

# Log: continuous samples with cumulative MU
log_cumulative_mu = log_data['mu']  # continuous corrected MU
log_x = log_data['x']
log_y = log_data['y']

# Interpolate LOG position at PLAN's MU values
interp_log_x = np.interp(plan_cumulative_mu, log_cumulative_mu, log_x)
interp_log_y = np.interp(plan_cumulative_mu, log_cumulative_mu, log_y)

# Compare: What position was the beam at when plan expected spot N?
diff_x = plan_x - interp_log_x
diff_y = plan_y - interp_log_y
```

**Physical Meaning**: "When the delivered MU reached the level expected for spot N, was the beam at position (x_N, y_N)?"

**Pros**:
- Direct comparison at discrete spot locations (clinically meaningful)
- Aligns with how treatment is planned (spot-by-spot delivery)
- Easier to interpret: "Did we hit each spot correctly?"
- No interpolation of plan data (plan positions are actual spot targets)

**Cons**:
- Only compares at spot MU values, not continuous
- May miss position errors during spot transitions
- Fewer data points for statistics

---

### Option B: Align Plan to Log's MU (Sample-Level Comparison)

Interpolate plan positions at log's sample MU values:

```python
# Interpolate PLAN position at LOG's MU values
interp_plan_x = np.interp(log_cumulative_mu, plan_cumulative_mu, plan_x)
interp_plan_y = np.interp(log_cumulative_mu, plan_cumulative_mu, plan_y)

# Compare: What position did plan expect at this delivered MU?
diff_x = interp_plan_x - log_x
diff_y = interp_plan_y - log_y
```

**Physical Meaning**: "At sample N with cumulative MU delivered, where did the plan expect the beam to be?"

**Pros**:
- Continuous comparison (all log samples used)
- More data points for statistics
- Similar to current time-based approach

**Cons**:
- Plan positions between spots are interpolated (not physically meaningful)
- Inter-spot comparison may be misleading
- Plan doesn't have positions between spots (beam is in transit)

---

### Option C: Hybrid Approach (Both Alignments)

Generate both comparisons and report separately:
1. **Spot-level errors**: Using Option A
2. **Transit errors**: Using Option B during inter-spot transit

This provides the most complete picture but adds complexity.

---

## Critical Considerations

### 1. MU Rate Variations
- Plan assumes ideal dose rate (from `LS_doserate.csv`)
- Actual delivery may have varying MU rate
- **This is exactly what MU-based comparison accounts for!** (Key advantage over time-based)

### 2. Interpolation Direction
| Approach | Interpolation | Physical Meaning |
|----------|---------------|------------------|
| Time-based | Plan → Log time | "At time T, where should beam be?" |
| MU-based A | Log → Plan MU | "At spot N's MU, where was beam?" |
| MU-based B | Plan → Log MU | "At MU level M, where should beam be?" |

**Recommendation**: Option A (align log to plan MU) because:
- Plan defines expected positions at specific MU levels
- We want to know: "Did we hit the spot when we delivered the planned MU?"

### 3. MU Unit Consistency ✅ VERIFIED
- **Plan MU**: From DICOM `CumulativeMetersetWeight` (already in correct units)
- **Log MU**: Corrected via `mu_correction.py` with energy-dependent factors
- Both represent the same physical quantity (monitor units)

### 4. Edge Cases
| Issue | Handling Strategy |
|-------|-------------------|
| Log MU doesn't reach final spot MU | Report incomplete delivery; only compare valid spots |
| Spots with zero MU | Skip these spots (no delivery expected) |
| Log MU exceeds plan MU | Truncate comparison; may indicate over-delivery |
| MU gaps in log data | Interpolation may be unreliable; flag warnings |

### 5. Settling Detection Adaptation
Current time-based settling detects when beam first arrives at target position. For MU-based:
- **Option**: Skip first N spots (settling spots) based on MU threshold
- **Alternative**: Use time-based settling for initial detection, then switch to MU-based for comparison

---

## Open Questions for User

1. **Comparison Direction?**
   - [ ] Option A: Spot-level (align log to plan MU) — Recommended
   - [ ] Option B: Sample-level (align plan to log MU)
   - [ ] Option C: Both (hybrid approach)

2. **Replace or Supplement?**
   - [ ] Replace time-based comparison entirely
   - [ ] Add MU-based as additional analysis mode
   - [ ] Make it configurable (config.yaml option)

3. **Settling Handling?**
   - [ ] Skip first N spots (configurable)
   - [ ] Use MU threshold (e.g., skip until X MU delivered)
   - [ ] Keep time-based settling detection, apply to MU-based

4. **Report Format?**
   - [ ] Same histogram style (-5 to 5 mm)
   - [ ] Add per-spot breakdown
   - [ ] Include both time-based and MU-based in report

---

## Research Findings Summary

### From Code Analysis

| Component | File | Key Finding |
|-----------|------|-------------|
| Plan MU extraction | `dicom_parser.py:120-127` | Per-spot MU from weight × total layer MU |
| Plan cumulative MU | `dicom_parser.py:139` | `np.cumsum(mus_array)` |
| Log MU parsing | `log_parser.py:109-110` | `np.cumsum(dose1_au)` |
| MU correction | `mu_correction.py:107-134` | Energy-dependent PCHIP interpolation |
| Current comparison | `calculator.py:111-115` | Time-based interpolation |

### Key Constants
- `MAX_SPEED = 2000.0` mm/s (scanning magnet speed)
- `MIN_DOSERATE = 1.4` MU/s
- `dose_dividing_factor = 10.0`

---

## Next Steps (After Decisions)

1. Implement chosen comparison mode in `calculator.py`
2. Add configuration option for comparison mode selection
3. Update report generator to display MU-based results
4. Add edge case handling (incomplete delivery, MU mismatches)
5. Update tests to cover MU-based comparison
6. Document new comparison mode in README
