# Low-MU Spots and Large Position Deviations

## Summary

Large position deviations (10-18mm) observed in the x-direction for certain layers are caused by planned spots with near-zero MU weights. These spots carry negligible dose (<0.5% of layer MU) but dominate the deviation statistics (max, std) because the current analysis weights all time samples equally regardless of delivered dose.

## Case Study: Patient 55758663, Beam 1G000:TX

### Observation

Layers 6-9 show large x-direction deviations in the PDF report:

| PDF Layer | layer_index | sigma_x (mm) | max_x (mm) | Total Layer MU |
|-----------|-------------|---------------|------------|----------------|
| 6         | 10          | 1.61          | 18.83      | 1.002          |
| 7         | 12          | 2.14          | 18.32      | 0.806          |
| 8         | 14          | 2.18          | 18.52      | 1.028          |
| 9         | 16          | 0.96          | 11.07      | 0.832          |

At the layer level, these are not low-MU layers. The total MU per layer is in the 0.8-1.0 range. The problem is at the **individual spot level**.

### Root Cause: Near-Zero MU Spots Within Layers

Per-spot MU analysis reveals an extremely skewed distribution. Taking layer 8 (layer_index 14) as a representative example:

```
N spots: 52
MU range: [0.000000, 0.081583]
Median MU: 0.000603
Spots with MU < 0.001: 27 / 52 (52%)
Spots with MU < 0.005: 27 / 52 (52%)
```

More than half the spots carry sub-0.001 MU weights — effectively zero dose.

### Mechanism

The plan trajectory reconstructor assigns dwell times proportional to spot MU. For a spot with MU = 0.000452 (the TPS minimum weight), the dwell time is ~0.3ms. The first several spots in each layer form a rapid sweep:

```
Spot  x(mm)   MU        Dwell(ms)   Cumulative(ms)
 0    -11.3   0.000000   0.000       0.000
 1     -5.3   0.000452   0.299       0.299
 2      0.6   0.000452   0.299       0.597
 3      6.6   0.000452   0.299       0.896
 4     12.6   0.000452   0.299       1.195
 5     18.5   0.069669  45.989      47.184   <-- first real dose spot
```

The plan sweeps ~30mm in 1.2ms across spots 0-4, then dwells at spot 5 for 46ms. The log samples at 60us intervals, producing ~20 samples during this sweep. The plan trajectory assumes instantaneous position jumps between spots, but the actual beam moves continuously. This produces large apparent position mismatches (10-18mm) during the sweep.

### Quantitative Impact

Grouping spots by MU threshold for each layer:

**Layer 6 (layer_index 10):**
- Low-MU spots (<0.005 MU): 6 spots, 8990 samples, mean max|diff_x| = 12.73 mm, total MU = 0.005 (0.5%)
- High-MU spots (>=0.005 MU): 1 spot, 2076 samples, mean max|diff_x| = 18.83 mm, total MU = 0.037 (3.7%)

**Layer 7 (layer_index 12):**
- Low-MU spots (<0.005 MU): 3 spots, 4218 samples, mean max|diff_x| = 12.40 mm, total MU = 0.001 (0.1%)
- High-MU spots (>=0.005 MU): 4 spots, 4672 samples, mean max|diff_x| = 15.22 mm, total MU = 0.110 (13.7%)

**Layer 8 (layer_index 14):**
- Low-MU spots (<0.005 MU): 6 spots, 8808 samples, mean max|diff_x| = 14.73 mm, total MU = 0.002 (0.2%)
- High-MU spots (>=0.005 MU): 1 spot, 2550 samples, mean max|diff_x| = 16.39 mm, total MU = 0.070 (6.8%)

**Layer 9 (layer_index 16):**
- Low-MU spots (<0.005 MU): 2 spots, 3378 samples, mean max|diff_x| = 10.54 mm, total MU = 0.001 (0.1%)
- High-MU spots (>=0.005 MU): 5 spots, 5804 samples, mean max|diff_x| = 7.18 mm, total MU = 0.224 (26.9%)

### Deviation Breakdown by Threshold (Layer 8)

| |diff_x| threshold | Samples  | % of total | Assigned spots' total MU |
|--------------------|----------|------------|--------------------------|
| > 1 mm             | 1514     | 13.3%      | 1.83 MU (multi-assigned) |
| > 2 mm             | 780      | 6.9%       | 1.41 MU                  |
| > 5 mm             | 371      | 3.3%       | 1.03 MU                  |
| > 10 mm            | 221      | 1.9%       | 0.62 MU                  |

The largest deviations (>5mm, >10mm) originate overwhelmingly from the near-zero MU spots in the initial sweep.

## Current Analysis Behavior

The calculator (`src/calculator.py:59-66`) computes unweighted statistics:

```python
def _calculate_axis_stats(diff):
    return {
        "mean": np.mean(diff),
        "std": np.std(diff),
        "rmse": np.sqrt(np.mean(diff ** 2)),
        "max_abs": np.max(np.abs(diff)),
        "p95_abs": np.percentile(np.abs(diff), 95),
    }
```

Every time sample contributes equally regardless of delivered MU. The near-zero MU sweep samples inflate `max_abs`, `std`, and `rmse`, producing misleading layer-level statistics.

The report aggregation (`src/report_generator.py:247-256`) further propagates this by computing unweighted means across layers.

## Recommendation

MU-weighted statistics would suppress these clinically irrelevant deviations. The infrastructure already exists:

- `plan_layer['mu']`: per-spot MU array (`src/dicom_parser.py:138`)
- `plan_layer['cumulative_mu']`: cumulative MU (`src/dicom_parser.py:139`)
- `log_data['mu']`: log-side cumulative MU (`src/log_parser.py:245`)

These are computed but not used in `calculator.py`.

A weighted analysis would:
1. Weight each time sample by the instantaneous MU rate (or the assigned spot's MU)
2. Use `np.average(diff, weights=mu_weights)` instead of `np.mean(diff)`
3. Reduce the impact of transit/sweep samples proportionally to their negligible dose contribution
4. Produce statistics that better reflect actual delivery accuracy for dose-relevant spots

## Date

2026-03-20
