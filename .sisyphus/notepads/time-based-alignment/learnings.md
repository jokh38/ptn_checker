# Learnings - Time-Based Alignment Implementation

## Initial Context
- Project: PTN Checker - Radiotherapy Plan and Log File Analyzer
- Goal: Replace MU-based plan/log alignment with time-based alignment
- Unit convention: All positions in `plan_timing.py` are in **cm** (matching Dicom_reader_F.py)
- Existing `src/dicom_parser.py` stores positions in **mm** (via F_SHI_spotP)

## Key Design Decisions
- D1: Unit convention - internal positions in cm, trajectory outputs converted back to mm
- D2: LS_doserate.csv is MATLAB format (not CSV) - needs custom parser
- D3: Line scanning uses continuous-motion delivery (no hold phase)
- D4: Plan-vs-log time range mismatch - log warning if >5% outside range
- D5: Test infrastructure needs NominalBeamEnergy on control points

## Reference Implementation
- `Dicom_reader_F.py` lines 102-164: `Layer.calculate_scan_times`
- Constants: MAX_SPEED = 2000 cm/s, MIN_DOSERATE = 1.4 MU/s

## Log
- 2026-03-19: Plan analysis started

- 2026-03-19: Added  and  via TDD. Implemented MATLAB-format doserate parser (strip , , , skip header), energy window lookup , and continuous-motion layer timing (segment[0] no time, MU<1e-7 uses distance/MAX_SPEED).

- 2026-03-19: Added tests/test_plan_timing.py and src/plan_timing.py via TDD. Implemented MATLAB-format doserate parser (strip brackets/semicolons and skip header), energy window lookup [E, E+0.3), and continuous-motion layer timing (segment[0] no time, MU<1e-7 uses distance/MAX_SPEED).
