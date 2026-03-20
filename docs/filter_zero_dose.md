# Filter Zero-Dose Transit Spots

## Status

Implementation spec

## Date

2026-03-20

## Problem

Some line-scanning plans encode "do not materially irradiate this position" by assigning the machine-minimum MU to a spot while the scanner moves at or near maximum speed. These spots are not true beam-off intervals. They are transit segments with negligible delivered dose.

The current analysis treats every time sample equally. As a result, transit samples associated with near-zero-dose spots dominate layer-level `std`, `rmse`, and `max` even when their cumulative MU contribution is negligible.

This produces clinically misleading layer metrics and PDF summaries for layers that contain many minimum-dose transit spots.

## Goal

Introduce a plan-side filter that identifies transit/min-dose spots and excludes their samples from dose-relevant position statistics while preserving raw debug visibility.

## Non-Goals

- Do not change PTN parsing or DICOM MU extraction semantics.
- Do not remove raw transit-inclusive metrics from debug outputs.
- Do not infer beam-off periods from the log.
- Do not redesign the full report layout in this change.

## Terminology

- `minimum-dose spot`: a spot whose planned MU is at or near the machine minimum MU.
- `transit/min-dose spot`: a minimum-dose spot that is part of a rapid scanning sweep and is intended to contribute negligible dose.
- `dose-relevant sample`: a reconstructed sample assigned to a non-transit spot.
- `raw metric`: a metric computed from all settled samples, including transit/min-dose samples.
- `filtered metric`: a metric computed only from dose-relevant samples.

## High-Level Design

The implementation will classify each planned spot in a layer as either `treatment` or `transit/min-dose` using plan-only features. That spot classification will be expanded to the reconstructed plan trajectory so each log-aligned sample inherits a boolean inclusion flag.

The calculator will produce two metric families:

- raw metrics: existing settled-sample metrics, unchanged in meaning
- filtered metrics: metrics computed after excluding samples assigned to transit/min-dose spots

The report generator will use filtered metrics for clinical summary and pass/fail checks, while raw metrics remain available for debugging and optional CSV output.

## Rationale

Filtering should be driven by the plan representation, not by exact equality to one MU value in the final sampled arrays.

Reasons:

- exact-value matching on `0.000452` is brittle under TPS formatting or machine-specific rounding
- the observed artifact is caused by a planning pattern, not just a single numeric constant
- near-minimum-MU spots slightly above the floor can still behave as zero-dose transit spots
- plan-side classification is more interpretable and testable than ad hoc sample filtering

## Detection Rule

### Recommended Rule

A planned spot is classified as `transit/min-dose` when all of the following are true:

1. `spot_mu <= ZERO_DOSE_MAX_MU`
2. `local_scan_speed_mm_s >= ZERO_DOSE_MIN_SCAN_SPEED_MM_S`
3. the spot is part of a contiguous run of low-MU candidates with length
   `>= ZERO_DOSE_MIN_RUN_LENGTH`, and at least one endpoint of that run is
   immediately adjacent to a spot classified as treatment

Additionally, an isolated machine-minimum spot (`mu ≈ ZERO_DOSE_MACHINE_MIN_MU`) at high scan speed is classified as transit if it is directly adjacent to a treatment spot, even if the run length is 1.

The default configuration should be conservative and transparent.

### Default Thresholds

These values are initial defaults and may need tuning against local data:

- `ZERO_DOSE_MAX_MU = 0.001`
- `ZERO_DOSE_MACHINE_MIN_MU = 0.000452`
- `ZERO_DOSE_MIN_SCAN_SPEED_MM_S = 10000`
- `ZERO_DOSE_MIN_RUN_LENGTH = 2`
- `ZERO_DOSE_KEEP_FIRST_ZERO_MU_SPOT = true`

Notes:

- `0.001 MU` captures the machine-minimum spot and similar near-floor spots.
- `10000 mm/s` corresponds to `10 m/s`; this is below the stated machine maximum of `20 m/s` and avoids requiring exact max-speed matching.
- The speed check is the primary discriminator between transit sweeps (~20000 mm/s) and genuine treatment spots (typically a few hundred mm/s). No relative-MU threshold is needed because the speed check already prevents false positives on layers where all spots have low MU.
- `ZERO_DOSE_MIN_RUN_LENGTH = 2` prevents a single isolated low-MU spot from being filtered solely because its MU is small. The separate machine-minimum fallback handles isolated spots at exactly the machine floor.
- When `ZERO_DOSE_KEEP_FIRST_ZERO_MU_SPOT = true`, the first spot in each layer with `mu == 0` is reclassified as treatment after the initial classification pass. It remains visible for debugging, and it does not break run detection for adjacent candidate spots.

### Removed: Relative MU Factor

An earlier version of this spec included a relative factor condition (`spot_mu <= ZERO_DOSE_RELATIVE_FACTOR * median_nonzero_spot_mu_in_layer`). This was removed because it prevented classification on layers where the median MU is itself near the machine minimum. On such layers, 5% of ~0.000453 is ~0.0000227, which is below the machine minimum, making the condition impossible to satisfy. The speed check alone is sufficient to distinguish transit from treatment.

### Implied Scan Speed

Scan speed is computed entirely from RT plan spot positions and plan-derived segment times. No log-side timing, MU, or position data is used for spot classification.

The derivation chain is:

`plan spot MU -> plan-derived segment time -> local scan speed`

The local scan speed for spot `i` (where `i >= 1`) is derived from its **incoming** segment — the segment from spot `i-1` to spot `i`:

```python
distance_mm = np.linalg.norm(positions[i] - positions[i - 1])
segment_time_s = segment_times_s[i]
speed_mm_s = distance_mm / segment_time_s if segment_time_s > 0 else np.inf
```

`segment_times_s` is produced by the trajectory builder with `segment_times_s[0] = 0` (no incoming segment for the first spot) and `segment_times_s[i]` = time for the segment from spot `i-1` to spot `i`.

The first spot in a layer (`i = 0`) has no incoming segment. Its speed is set to `0`, so it cannot be classified as transit by the speed check alone.

### Run-Based Context

Low MU alone is not sufficient. A spot should only be marked as transit/min-dose when it is part of a run of consecutive near-minimum-MU spots or directly adjacent to such a run that connects to a higher-MU spot.

This prevents isolated low-MU clinical spots from being dropped without context.

## Data Model Changes

### `src/dicom_parser.py`

Extend each layer dictionary with plan-side spot metadata:

- `spot_is_transit_min_dose`: `np.ndarray[bool]`, shape `(n_spots,)`
- `spot_scan_speed_mm_s`: `np.ndarray[float]`, shape `(n_spots,)`

The classification is computed during `parse_dcm_file`, after `segment_times_s` becomes available from the trajectory builder. Classification runs unconditionally — the `enabled` flag in config controls only whether filtered metrics are computed downstream in the calculator.

### `src/calculator.py`

Expand the spot classification to the sampled comparison domain:

- `sample_is_transit_min_dose`: `np.ndarray[bool]`, shape `(n_log_samples,)`
- `sample_is_included_filtered_stats`: `np.ndarray[bool]`, shape `(n_log_samples,)`

Also emit summary counters:

- `num_filtered_samples`
- `num_included_samples`
- `filtered_sample_fraction`
- `filtered_mu_fraction_estimate`

### `config.yaml`

Add a new configuration block:

```yaml
zero_dose_filter:
  enabled: true
  max_mu: 0.001
  min_scan_speed_mm_s: 10000
  min_run_length: 2
  keep_first_zero_mu_spot: true
  report_mode: filtered
```

`report_mode` values:

- `filtered`: report and pass/fail use filtered metrics
- `raw`: preserve legacy behavior
- `both`: report filtered metrics primarily and include raw metrics in debug outputs

When `zero_dose_filter.enabled = false`, spot classification still runs in `parse_dcm_file` (the results are stored in the layer dictionary for debug inspection), but the calculator does not compute filtered metrics. All report metrics use settled samples only, matching legacy behavior. The `filtered_*` result fields are not emitted.

## Algorithm

### Phase 1: Spot Classification

For each layer:

1. Load `positions`, `mu`, `segment_times_s`.
2. Compute per-spot local scan speed.
3. Mark spots as low-MU candidates if `mu <= ZERO_DOSE_MAX_MU` and `speed >= ZERO_DOSE_MIN_SCAN_SPEED_MM_S`.
4. Group consecutive candidates into runs.
5. Mark a run as `transit/min-dose` only if:
   - the run length is `>= ZERO_DOSE_MIN_RUN_LENGTH`
   - at least one endpoint of the run is immediately adjacent to a higher-MU treatment spot
6. Additionally, mark isolated machine-minimum spots (`mu ≈ ZERO_DOSE_MACHINE_MIN_MU`) at high scan speed as transit if directly adjacent to a treatment spot.
7. Apply `ZERO_DOSE_KEEP_FIRST_ZERO_MU_SPOT` after run classification.
8. Save the per-spot boolean mask and diagnostic reasons.

### Phase 2: Sample Assignment

Map each log-aligned sample to the active plan spot segment.

Recommended implementation:

- build a per-sample spot index using the reconstructed plan timeline
- assign each sample to the spot whose reconstructed time segment contains the sample timestamp
- if a sample falls exactly on a segment boundary, assign it to the later spot
- propagate `spot_is_transit_min_dose[spot_index]` to `sample_is_transit_min_dose`

Do not infer this directly from interpolated MU alone. The classification source of truth must stay on the plan spot structure.

### Phase 3: Metric Computation

Keep the existing settling exclusion first:

```python
settled_mask = ~is_settling
filtered_mask = settled_mask & ~sample_is_transit_min_dose
```

Compute:

- raw metrics on `diff_x[settled_mask]`, `diff_y[settled_mask]`
- filtered metrics on `diff_x[filtered_mask]`, `diff_y[filtered_mask]`

If `filtered_mask` is empty, fall back to settled raw metrics and emit a warning in logs plus a result flag:

- `filtered_stats_fallback_to_raw = True`

## Metrics Policy

### Layer-Level Results

Retain existing field names for raw metrics to avoid breaking downstream code:

- `mean_diff_x`
- `mean_diff_y`
- `std_diff_x`
- `std_diff_y`
- `rmse_x`
- `rmse_y`
- `max_abs_diff_x`
- `max_abs_diff_y`
- `p95_abs_diff_x`
- `p95_abs_diff_y`

Add explicit filtered metrics:

- `filtered_mean_diff_x`
- `filtered_mean_diff_y`
- `filtered_std_diff_x`
- `filtered_std_diff_y`
- `filtered_rmse_x`
- `filtered_rmse_y`
- `filtered_max_abs_diff_x`
- `filtered_max_abs_diff_y`
- `filtered_p95_abs_diff_x`
- `filtered_p95_abs_diff_y`

### Report Policy

`src/report_generator.py` should select metrics according to `zero_dose_filter.report_mode`.

Default behavior after this change:

- summary table uses filtered metrics
- pass/fail uses filtered metrics
- layer plots use filtered metrics
- raw metrics remain available for optional debug display and CSV inspection
- the PDF summary page includes a visible note when zero-dose transit filtering is active
- the PDF includes per-layer excluded sample count and excluded MU fraction, either in the summary table or a supplementary table

Mode-specific output policy:

| Mode | PDF summary | PDF pass/fail | CSV | Debug log |
|------|-------------|---------------|-----|-----------|
| `filtered` | filtered | filtered | both | both |
| `raw` | raw | raw | raw | raw |
| `both` | filtered | filtered | both | both |

## CSV and Debug Output

When debug CSV is enabled, add these columns:

- `sample_is_transit_min_dose`
- `sample_is_included_filtered_stats`
- `assigned_spot_index`
- `assigned_spot_mu`
- `assigned_spot_scan_speed_mm_s`

This is required so users can audit which samples were excluded and why.

## Affected Modules

- `src/dicom_parser.py`
  - compute spot-level transit/min-dose classification
- `src/calculator.py`
  - propagate spot classification to samples
  - compute raw and filtered metric families
- `src/report_generator.py`
  - select report metric family based on config
- `config.yaml`
  - add `zero_dose_filter` configuration block

No changes are required in:

- `src/log_parser.py`
- `src/mu_correction.py`

## Edge Cases

### All Spots Are Near-Zero MU

If a layer contains no clear treatment spot after classification:

- do not exclude the entire layer silently
- fall back to raw settled metrics
- mark the layer with `filtered_stats_fallback_to_raw = True`

### Isolated Low-MU Clinical Spot

If a spot is low MU but not part of a high-speed transit run:

- keep it as a treatment spot
- include it in filtered metrics

### Zero Segment Time

If `segment_times_s[i] == 0`:

- treat speed as `inf` for diagnostic purposes
- require run-based context before classifying as transit/min-dose

### First Spot in Layer

Because the first spot (`i = 0`) has no incoming segment:

- its scan speed is set to `0`
- it cannot satisfy the speed threshold and will not be classified as transit by the speed check
- if it has `mu == 0` and `ZERO_DOSE_KEEP_FIRST_ZERO_MU_SPOT` is true, it is explicitly kept as treatment regardless of any other classification

## Validation Plan

### Unit and Component Validation

Add tests for:

- low-MU run detection in a synthetic layer
- isolated low-MU spot retained as treatment
- sample-level propagation of spot classification
- fallback when filtered mask is empty
- report mode selection in summary and pass/fail logic

Recommended commands:

```bash
python -m pytest
```

This is `component validated` only if the above tests pass.

### Data Validation

Run against known local datasets from the project runbook:

- `G1`: `/home/jokh38/MOQUI_SMC/data/SHI_log/55758663`
- `G2`: `/home/jokh38/MOQUI_SMC/data/SHI_log/55061194`

For each dataset, compare before vs after:

- number of excluded samples
- excluded MU fraction
- layer-level raw vs filtered `std`, `rmse`, `max`, `p95`
- pass/fail changes
- the number of treatment spots incorrectly classified as transit

Acceptance criteria:

- For the known problematic layers described in `LOWMU_LARGEDEV.md`, filtered `std_diff_x`, `rmse_x`, and `max_abs_diff_x` must decrease relative to raw metrics.
- Excluded MU fraction must remain below `1%` of layer MU for layers where filtering is active, unless explicitly flagged for manual review.
- The number of treatment spots incorrectly classified as transit must be `0` on the validation datasets.
- PDF output must visibly indicate whether zero-dose transit filtering was enabled.

This should be reported with aggregate statistics across affected layers, not a single cherry-picked example.

This is `end-to-end validated` only if the report generation command completes and the output metrics are reviewed on real data.

## Observations

- The repository already computes plan-side per-spot MU and cumulative MU.
- The repository already reconstructs per-layer segment timing.
- The main missing piece is explicit spot classification and propagation of that classification into statistics/reporting.

## Assumptions

- The machine-minimum-MU spots in these line-scanning plans are intended as transit placeholders rather than clinically meaningful spots.
- A combined MU-plus-speed rule is sufficient to distinguish transit placeholders from genuine low-MU treatment spots.
- Existing downstream consumers can tolerate additional result fields as long as legacy raw field names remain unchanged.

## Implementation Decision

Proceed with a plan-side `transit/min-dose` classifier and dual raw/filtered metric outputs. Use filtered metrics as the default report basis, keep raw metrics for debugging, and make the behavior configurable in `config.yaml`.
