# LOGFILE Spec Deviation Review

## Scope

This document records a static review of the beam-intensity conversion described in Section 2.2.2 of [`LOGFILE_SPEC.md`](/home/jokh38/MOQUI_SMC/ptn_checker/LOGFILE_SPEC.md) against the current implementation in [`src/mu_correction.py`](/home/jokh38/MOQUI_SMC/ptn_checker/src/mu_correction.py).

Validation status: `component validated`

This is not an end-to-end validation. No claim is made here that delivered MU values are correct or incorrect in full workflow execution.

## Source References

- Spec formula: [`LOGFILE_SPEC.md:120`](/home/jokh38/MOQUI_SMC/ptn_checker/LOGFILE_SPEC.md#L120)
- Monitor range table: [`LOGFILE_SPEC.md:123`](/home/jokh38/MOQUI_SMC/ptn_checker/LOGFILE_SPEC.md#L123)
- Factor definition: [`LOGFILE_SPEC.md:140`](/home/jokh38/MOQUI_SMC/ptn_checker/LOGFILE_SPEC.md#L140)
- Implementation entry point: [`src/mu_correction.py:107`](/home/jokh38/MOQUI_SMC/ptn_checker/src/mu_correction.py#L107)
- Monitor range factors: [`src/mu_correction.py:87`](/home/jokh38/MOQUI_SMC/ptn_checker/src/mu_correction.py#L87)
- README-supported range statement: [`README.md:157`](/home/jokh38/MOQUI_SMC/ptn_checker/README.md#L157)

## Spec Summary

Section 2.2.2 defines beam intensity as:

```text
Intensity (MUraw/s) = Monitor Full Range × (measured value / 65535) × factor
factor = 1 / DM_CALC_FACTOR_B
```

The spec defines `DOSE1_RANGE` to `Monitor Full Range` as:

| Code | Full Range |
| ---- | ---------- |
| 1 | 160 nA |
| 2 | 470 nA |
| 3 | 1400 nA |
| 4 | 4200 nA |
| 5 | 12600 nA |

## Implementation Summary

The current code applies this correction chain:

```text
corrected = dose1_au
          * proton_per_dose_factor(energy)
          * dose_per_mu_count_factor(energy)
          * monitor_range_factor(code)
          / dose_dividing_factor
```

Relevant implementation details:

- `dose1_au` is used directly from parsed 16-bit values.
- `monitor_range_factor(code)` is hardcoded as a ratio table relative to code `2`.
- The code does not explicitly divide by `65535`.
- The code does not read `DM_CALC_FACTOR_B` from any database source.
- The correction chain is documented as adapted from `mqi_interpreter`.

## Confirmed Findings

### 1. `DOSE1_RANGE = 1` is not supported in the implementation

[`src/mu_correction.py:89`](/home/jokh38/MOQUI_SMC/ptn_checker/src/mu_correction.py#L89) defines factors only for codes `2`, `3`, `4`, and `5`.

For any other code, [`src/mu_correction.py:95`](/home/jokh38/MOQUI_SMC/ptn_checker/src/mu_correction.py#L95) logs a warning and returns `1.0`.

The spec explicitly includes code `1 = 160 nA`, so the current implementation is not spec-complete.

Impact:

- If a valid layer uses `DOSE1_RANGE = 1`, the current fallback would apply the same scale as code `2`.
- Relative to the spec range table, that would over-scale intensity by `470 / 160 = 2.9375x`.

### 2. The implementation does not follow the Section 2.2.2 formula structure

The spec explicitly requires:

```text
Monitor Full Range × (measured value / 65535) × (1 / DM_CALC_FACTOR_B)
```

The implementation instead uses:

```text
dose1_au × energy-dependent factors × hardcoded range ratio ÷ 10.0
```

Confirmed deviations:

- No explicit `measured value / 65535`
- No explicit `DM_CALC_FACTOR_B`
- No database lookup for `DM_CALC_FACTOR`
- Range scaling encoded as ratios to code `2`, not as direct absolute full-range values

This is a real implementation/spec deviation at the formula-definition level.

### 3. The repository documents a narrower supported range than the spec

[`README.md:161`](/home/jokh38/MOQUI_SMC/ptn_checker/README.md#L161) states:

```text
DOSE1_RANGE: Monitor range code (2-5) for dose scaling
```

That narrows supported inputs compared with the spec, which defines `1-5`.

This means the current repository behavior appears intentional at the documentation level, but still deviates from the spec document under review.

## Observations

- The hardcoded factors for codes `3`, `4`, and `5` are numerically equal to `1400/470`, `4200/470`, and `12600/470`.
- The bundled sample `Data_ex/**/PlanRange.txt` files in this repository contain only `DOSE1_RANGE = 2`.
- Because of that dataset limitation, the unsupported code `1` path is not exercised by the checked-in example data.

## Assumptions And Unknowns

### Assumption

This review assumes Section 2.2.2 of [`LOGFILE_SPEC.md`](/home/jokh38/MOQUI_SMC/ptn_checker/LOGFILE_SPEC.md) is the intended authority for this codebase.

### Unknown

It is not yet proven that the current implementation produces incorrect final MU values in practice.

Possible explanations that still need verification:

- The missing `/65535` may be absorbed into legacy calibration constants.
- `dose_dividing_factor = 10.0` may be part of an equivalent reformulation.
- The energy-dependent factors inherited from `mqi_interpreter` may encode part of the omitted scaling.
- The code may intentionally target a narrower, empirically calibrated workflow rather than literal spec conformance.

Until reference-data comparison is performed, this document should be interpreted as a spec-deviation finding, not a full numerical-invalidity proof.

## Recommended Follow-Up

1. Add explicit support for `DOSE1_RANGE = 1` if spec compliance is required.
2. Decide whether this project is intended to be:
   - spec-faithful to Section 2.2.2, or
   - intentionally aligned to `mqi_interpreter`
3. If `mqi_interpreter` behavior is intentional, document the derivation or rationale for:
   - no explicit `/65535`
   - no `DM_CALC_FACTOR_B` lookup
   - use of `dose_dividing_factor = 10.0`
4. Add unit tests for monitor range handling, including code `1` and unknown-code behavior.
5. Validate against reference data before changing the formula path.

## Verification Notes

This document was produced from static code and document review plus repository sample-data inspection.

Commands used during review:

```bash
sed -n '1,260p' LOGFILE_SPEC.md
sed -n '1,220p' src/mu_correction.py
sed -n '140,260p' README.md
python - <<'PY'
import pandas as pd
from pathlib import Path
for p in Path('Data_ex').rglob('PlanRange.txt'):
    df = pd.read_csv(p)
    print(p, sorted(df['DOSE1_RANGE'].dropna().unique().tolist()))
PY
```
