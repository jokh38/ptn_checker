# Plan: Settling Artifact Filter for Beam Position Deviation

## TL;DR

> **Quick Summary**: Add beam settling detection to filter out position deviation artifacts caused by magnet inertia at layer start. When the beam transitions to a new layer, it cannot instantly reach the planned position, causing artificial deviations in the first few samples.
> 
> **Deliverables**:
> - Settling detection function in calculator.py
> - Configuration parameters in scv_init files
> - Unit tests for all settling scenarios
> - Debug CSV with `is_settling` flag column
> - Statistics calculated on settled samples only
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Config → Detection Logic → Tests → Integration

---

## Context

### Original Request
G1 shows larger X deviation than G2 (0.230mm vs 0.190mm std). Analysis revealed this is caused by beam settling artifacts - the scanning magnet cannot instantly reach the planned position at layer start due to physical inertia. The deviation calculation currently includes ALL samples, including those where the beam hasn't settled yet.

### Interview Summary
**Key Discussions**:
- **Settling criteria**: Position threshold - start counting when |log - plan| < threshold (0.5mm) for N consecutive samples
- **Filter scope**: Layer start only - filter at the beginning of each layer
- **Output handling**: Mark as 'settling' flag - include samples in debug CSV but mark them

**Research Findings**:
- Large deviations occur at: (1) beam/layer start, (2) layer transitions (40-60mm distances), (3) within-layer large jumps
- Beam "lags behind" plan position during rapid transitions - log position is always BEHIND plan when moving
- G1 has 35 layers with layer-to-layer distances of 40-60mm
- Only 1.6% of samples have |deviation| > 0.5mm, but they skew the max deviation significantly

### Metis Review
**Identified Gaps** (addressed):
- **Edge cases**: Empty layers, never-settles scenario, instant settling, noisy signal - all handled
- **Configuration design**: Added validation, default disabled for backward compatibility
- **Test impact**: Major - all tests checking statistics values will need updates

---

## Work Objectives

### Core Objective
Filter beam settling artifacts from deviation statistics while maintaining data transparency through flagging.

### Concrete Deliverables
- `src/calculator.py`: Add settling detection and flagging logic
- `scv_init_G1.txt`, `scv_init_G2.txt`: Add configuration parameters
- `src/config_loader.py`: Add new configuration keys
- `tests/test_calculator.py`: Add settling detection tests
- `tests/test_config_loader.py`: Add configuration validation tests

### Definition of Done
- [ ] Settling detection works with position threshold + consecutive samples
- [ ] Statistics exclude settling samples when enabled
- [ ] Debug CSV includes `is_settling` column
- [ ] All existing tests pass with SETTLING_ENABLED=off
- [ ] New tests cover all edge cases
- [ ] Configuration validation prevents invalid values
- [ ] Backward compatible (default disabled)

### Must Have
- Position threshold-based settling detection
- Consecutive samples requirement (avoid noise issues)
- Layer start only scope (no within-layer transition detection)
- `is_settling` flag in results and CSV output
- Statistics calculated on settled samples only
- Configuration parameters in scv_init files
- Default disabled for backward compatibility

### Must NOT Have (Guardrails)
- NO within-layer transition detection (scope limited to layer start)
- NO changes to report visualization
- NO removal of samples from arrays (use masking)
- NO behavior changes when SETTLING_ENABLED=off
- NO changes to beam filtering logic
- NO changes to plan timing logic

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (TDD approach)
- **Framework**: pytest
- **TDD**: Each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Library/Module**: Use Bash (python -m pytest) — Import, call functions, compare output

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — configuration + detection logic):
├── Task 1: Add settling configuration parameters [quick]
├── Task 2: Implement settling detection function [deep]
├── Task 3: Add is_settling flag to calculator results [quick]
└── Task 4: Update CSV output with settling flag [quick]

Wave 2 (After Wave 1 — tests + integration):
├── Task 5: Add unit tests for settling detection [unspecified-high]
├── Task 6: Add edge case tests [unspecified-high]
├── Task 7: Update existing tests for backward compatibility [quick]
└── Task 8: Integration test with real G1 data [unspecified-high]

Critical Path: Task 2 → Task 5 → Task 8
Parallel Speedup: ~50% faster than sequential
Max Concurrent: 4 (Wave 1)
```

### Dependency Matrix

- **1-4**: — — 5-8
- **5**: 2 — 6, 7
- **6**: 2, 5 — 8
- **7**: 1, 3 — 8
- **8**: 5, 6, 7 — —

### Agent Dispatch Summary

- **1**: **4** — T1→`quick`, T2→`deep`, T3→`quick`, T4→`quick`
- **2**: **4** — T5→`unspecified-high`, T6→`unspecified-high`, T7→`quick`, T8→`unspecified-high`

---

## TODOs

- [ ] 1. Add settling configuration parameters

  **What to do**:
  - Add configuration keys to `config_loader.py`: `SETTLING_ENABLED`, `SETTLING_THRESHOLD_MM`, `SETTLING_WINDOW_SAMPLES`, `SETTLING_CONSECUTIVE_SAMPLES`
  - Add default values to `scv_init_G1.txt` and `scv_init_G2.txt`
  - Add configuration validation function `_validate_settling_config()`
  - Default: SETTLING_ENABLED=off for backward compatibility

  **Must NOT do**:
  - Do NOT change any existing configuration keys
  - Do NOT enable settling by default

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple configuration additions following existing patterns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Tasks 5, 7
  - **Blocked By**: None (can start immediately)

  **References**:
  - `src/config_loader.py:1-50` - Existing configuration loading pattern
  - `scv_init_G1.txt:88-93` - Existing config file format (add after FILTERED_BEAM_ON_OFF)

  **Acceptance Criteria**:
  - [ ] `parse_scv_init('scv_init_G1.txt')['SETTLING_THRESHOLD_MM'] == 0.5`
  - [ ] Validation rejects: threshold <= 0, consecutive > window
  - [ ] Default SETTLING_ENABLED=off

  **QA Scenarios**:
  ```
  Scenario: Config loads with valid settling parameters
    Tool: Bash (python -c)
    Steps:
      1. from src.config_loader import parse_scv_init
      2. config = parse_scv_init('scv_init_G1.txt')
      3. assert config['SETTLING_THRESHOLD_MM'] == 0.5
      4. assert config['SETTLING_CONSECUTIVE_SAMPLES'] == 10
    Expected Result: All assertions pass
    Evidence: .sisyphus/evidence/task-01-config-load.txt

  Scenario: Config validation rejects invalid threshold
    Tool: Bash (python -c)
    Steps:
      1. from src.calculator import _validate_settling_config
      2. _validate_settling_config({'SETTLING_ENABLED': 'on', 'SETTLING_THRESHOLD_MM': -0.5})
    Expected Result: ValueError raised with message about threshold > 0
    Evidence: .sisyphus/evidence/task-01-validation.txt
  ```

  **Commit**: YES
  - Message: `feat(config): add settling detection configuration parameters`
  - Files: scv_init_G1.txt, scv_init_G2.txt, src/config_loader.py

- [ ] 2. Implement settling detection function

  **What to do**:
  - Add `_detect_settling()` function to `calculator.py`
  - Input: diff_x, diff_y arrays, config parameters
  - Output: settling_index (first settled sample), settling_status
  - Algorithm: Find first N consecutive samples where |diff| < threshold (both X and Y)
  - Handle edge cases: empty arrays, never settles, instant settling

  **Must NOT do**:
  - Do NOT modify main `calculate_differences_for_layer()` signature yet (Task 3)
  - Do NOT add within-layer transition detection
  - Do NOT remove any samples from arrays

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Core algorithm implementation with multiple edge cases
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Tasks 5, 6
  - **Blocked By**: None (can start immediately)

  **References**:
  - `src/calculator.py:18-57` - Existing difference calculation logic
  - `src/log_parser.py:151-201` - Existing filtering pattern (use as reference)

  **Acceptance Criteria**:
  - [ ] `_detect_settling()` returns tuple (settling_index, settling_status)
  - [ ] settling_status ∈ {'settled', 'never_settled', 'insufficient_data'}
  - [ ] Works when first sample already settled (returns 0, 'settled')
  - [ ] Works when never settles (returns len(diff_x), 'never_settled')
  - [ ] Works with < 10 samples (returns 0, 'insufficient_data')

  **QA Scenarios**:
  ```
  Scenario: Normal settling detection
    Tool: Bash (python -c)
    Steps:
      1. from src.calculator import _detect_settling
      2. diff_x = [1.0, 0.8, 0.4, 0.3, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1]
      3. diff_y = [0.5, 0.4, 0.3, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]
      4. idx, status = _detect_settling(diff_x, diff_y, threshold=0.5, consecutive=3)
      5. assert idx == 4  # First settled sample at index 4
      6. assert status == 'settled'
    Expected Result: All assertions pass
    Evidence: .sisyphus/evidence/task-02-normal-settling.txt

  Scenario: Never settles
    Tool: Bash (python -c)
    Steps:
      1. from src.calculator import _detect_settling
      2. diff_x = [2.0, 1.8, 1.6, 1.4, 1.2, 1.0, 0.9, 0.8, 0.7, 0.6]
      3. diff_y = [2.0, 1.8, 1.6, 1.4, 1.2, 1.0, 0.9, 0.8, 0.7, 0.6]
      4. idx, status = _detect_settling(diff_x, diff_y, threshold=0.5, consecutive=3)
      5. assert status == 'never_settled'
    Expected Result: status == 'never_settled'
    Evidence: .sisyphus/evidence/task-02-never-settles.txt
  ```

  **Commit**: YES
  - Message: `feat(calculator): implement beam settling detection`
  - Files: src/calculator.py

- [ ] 3. Add is_settling flag to calculator results

  **What to do**:
  - Modify `calculate_differences_for_layer()` to call `_detect_settling()`
  - Add `is_settling` boolean array to results (same length as diff_x)
  - Add settling metadata: `settling_index`, `settling_samples_count`, `settling_status`
  - Skip settling detection if SETTLING_ENABLED=off
  - Calculate statistics on settled samples only when enabled

  **Must NOT do**:
  - Do NOT remove samples from arrays
  - Do NOT change behavior when SETTLING_ENABLED=off

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward integration following existing patterns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Tasks 5, 7, 8
  - **Blocked By**: None (can start immediately, but Task 2 function must exist)

  **References**:
  - `src/calculator.py:56-131` - Existing statistics calculation
  - `src/calculator.py:83-85` - Existing result key pattern

  **Acceptance Criteria**:
  - [ ] `results['is_settling']` is boolean numpy array
  - [ ] `results['settling_index']` is integer
  - [ ] `results['settling_status']` is string
  - [ ] Statistics (mean, std, rmse, max, p95) calculated on settled samples only
  - [ ] When SETTLING_ENABLED=off: no settling keys in results, all samples in statistics

  **QA Scenarios**:
  ```
  Scenario: Results include settling flag when enabled
    Tool: Bash (python -c)
    Steps:
      1. Create test plan_layer and log_data with settling
      2. Call calculate_differences_for_layer with SETTLING_ENABLED=on
      3. assert 'is_settling' in results
      4. assert 'settling_index' in results
      5. assert sum(results['is_settling']) == results['settling_samples_count']
    Expected Result: All assertions pass
    Evidence: .sisyphus/evidence/task-03-flag-enabled.txt

  Scenario: No settling keys when disabled
    Tool: Bash (python -c)
    Steps:
      1. Create test plan_layer and log_data
      2. Call calculate_differences_for_layer with SETTLING_ENABLED=off
      3. assert 'is_settling' not in results
      4. assert 'settling_index' not in results
    Expected Result: No settling keys in results
    Evidence: .sisyphus/evidence/task-03-flag-disabled.txt
  ```

  **Commit**: YES
  - Message: `feat(calculator): add is_settling flag to results`
  - Files: src/calculator.py

- [ ] 4. Update CSV output with settling flag

  **What to do**:
  - Add `is_settling` column to debug CSV when SETTLING_ENABLED=on
  - Column should be 1 for settling samples, 0 for settled samples
  - Only add column when settling detection is enabled

  **Must NOT do**:
  - Do NOT change CSV format when SETTLING_ENABLED=off

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple CSV output modification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 8
  - **Blocked By**: Task 3 (needs is_settling array)

  **References**:
  - `src/calculator.py:67-81` - Existing CSV output logic

  **Acceptance Criteria**:
  - [ ] CSV header includes `is_settling` when enabled
  - [ ] is_settling values are 0 or 1
  - [ ] No is_settling column when disabled

  **QA Scenarios**:
  ```
  Scenario: CSV includes is_settling column when enabled
    Tool: Bash (python -c)
    Steps:
      1. Run calculate_differences_for_layer with save_to_csv=True, SETTLING_ENABLED=on
      2. Read CSV file
      3. assert 'is_settling' in header
      4. assert all values are 0 or 1
    Expected Result: is_settling column present with 0/1 values
    Evidence: .sisyphus/evidence/task-04-csv-enabled.csv

  Scenario: CSV unchanged when disabled
    Tool: Bash (python -c)
    Steps:
      1. Run calculate_differences_for_layer with save_to_csv=True, SETTLING_ENABLED=off
      2. Read CSV file
      3. assert 'is_settling' not in header
    Expected Result: No is_settling column
    Evidence: .sisyphus/evidence/task-04-csv-disabled.csv
  ```

  **Commit**: YES
  - Message: `feat(calculator): add is_settling column to debug CSV`
  - Files: src/calculator.py

- [ ] 5. Add unit tests for settling detection

  **What to do**:
  - Create test functions in `tests/test_calculator.py`:
    - `test_settling_detection_normal()` - beam settles after N samples
    - `test_settling_detection_instant()` - beam already settled at start
    - `test_settling_detection_disabled()` - feature disabled
    - `test_settling_statistics_exclude_settling()` - stats on settled only
  - Use pytest fixtures for test data
  - Each test should be self-contained

  **Must NOT do**:
  - Do NOT modify existing tests (Task 7 handles that)
  - Do NOT use real DICOM/PTN files (use synthetic data)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: TDD tests require careful design
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Tasks 1-4 complete)
  - **Blocks**: Task 8
  - **Blocked By**: Task 2 (needs _detect_settling function)

  **References**:
  - `tests/test_calculator.py:1-100` - Existing test patterns
  - `tests/conftest.py` - Test fixtures

  **Acceptance Criteria**:
  - [ ] All 4 test functions pass
  - [ ] Tests cover: normal, instant, disabled, statistics exclusion
  - [ ] Each test is independent (no shared state)

  **QA Scenarios**:
  ```
  Scenario: All settling tests pass
    Tool: Bash (python -m pytest)
    Steps:
      1. python -m pytest tests/test_calculator.py -k settling -v
    Expected Result: 4 tests pass, 0 failures
    Evidence: .sisyphus/evidence/task-05-tests-pass.txt
  ```

  **Commit**: YES
  - Message: `test(calculator): add settling detection unit tests`
  - Files: tests/test_calculator.py

- [ ] 6. Add edge case tests for settling detection

  **What to do**:
  - Create test functions for edge cases:
    - `test_settling_never_settles()` - beam never reaches threshold
    - `test_settling_insufficient_data()` - < 10 samples
    - `test_settling_empty_layer()` - 0 samples
    - `test_settling_noisy_signal()` - oscillates around threshold
    - `test_settling_config_validation()` - invalid config values
  - Verify error handling and fallback behavior

  **Must NOT do**:
  - Do NOT add new error types (use ValueError)
  - Do NOT change production code behavior to make tests pass

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Edge case testing requires thorough analysis
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Task 5)
  - **Blocks**: Task 8
  - **Blocked By**: Task 2 (needs _detect_settling), Task 5 (builds on)

  **References**:
  - `tests/test_calculator.py` - Existing test patterns
  - Metis analysis edge cases (in draft)

  **Acceptance Criteria**:
  - [ ] All 5 edge case tests pass
  - [ ] Tests verify correct error messages / fallback behavior
  - [ ] Config validation rejects invalid values

  **QA Scenarios**:
  ```
  Scenario: Edge case tests pass
    Tool: Bash (python -m pytest)
    Steps:
      1. python -m pytest tests/test_calculator.py -k "settling and (never or insufficient or empty or noisy or config)" -v
    Expected Result: 5 tests pass, 0 failures
    Evidence: .sisyphus/evidence/task-06-edge-cases.txt
  ```

  **Commit**: YES
  - Message: `test(calculator): add settling detection edge case tests`
  - Files: tests/test_calculator.py, tests/test_config_loader.py

- [ ] 7. Update existing tests for backward compatibility

  **What to do**:
  - Review all existing tests in `tests/test_calculator.py`
  - Ensure tests pass with SETTLING_ENABLED=off (default)
  - Add explicit config parameter to tests that would be affected
  - Update any hardcoded expected values if necessary
  - Verify no test behavior changes when settling is disabled

  **Must NOT do**:
  - Do NOT enable settling by default in tests
  - Do NOT skip or delete existing tests

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Routine test maintenance
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 8
  - **Blocked By**: Task 1 (needs config), Task 3 (needs flag)

  **References**:
  - `tests/test_calculator.py` - All existing tests
  - `tests/test_main.py` - Integration tests

  **Acceptance Criteria**:
  - [ ] All existing tests pass without modification when SETTLING_ENABLED=off
  - [ ] No test behavior changes
  - [ ] `python -m pytest tests/` passes with 0 failures

  **QA Scenarios**:
  ```
  Scenario: All existing tests pass
    Tool: Bash (python -m pytest)
    Steps:
      1. python -m pytest tests/test_calculator.py tests/test_main.py -v
    Expected Result: All tests pass, 0 failures
    Evidence: .sisyphus/evidence/task-07-backward-compat.txt
  ```

  **Commit**: YES
  - Message: `test(calculator): ensure backward compatibility with settling disabled`
  - Files: tests/test_calculator.py

- [ ] 8. Integration test with real G1 data

  **What to do**:
  - Run full analysis on G1 data with SETTLING_ENABLED=on
  - Verify:
    1. No crashes or errors
    2. Debug CSV has is_settling column
    3. Statistics values changed (lower deviation expected)
    4. PDF report generated successfully
  - Compare before/after statistics to verify settling filtering works
  - Save evidence files

  **Must NOT do**:
  - Do NOT modify production code
  - Do NOT add new features

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Real data testing requires careful verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (last task)
  - **Blocks**: None
  - **Blocked By**: Tasks 1-7 (all implementation and tests complete)

  **References**:
  - `/home/jokh38/MOQUI_SMC/data/SHI_log/55758663` - G1 test data
  - `main.py` - Entry point

  **Acceptance Criteria**:
  - [ ] Analysis runs without errors
  - [ ] Debug CSV includes is_settling column
  - [ ] Statistics with settling enabled differ from disabled
  - [ ] PDF report generated
  - [ ] Evidence saved to .sisyphus/evidence/

  **QA Scenarios**:
  ```
  Scenario: G1 analysis with settling enabled
    Tool: Bash (python main.py)
    Steps:
      1. Enable SETTLING_ENABLED=on in scv_init_G1.txt
      2. python main.py --log_dir /home/jokh38/MOQUI_SMC/data/SHI_log/55758663 --dcm_file "/home/jokh38/MOQUI_SMC/data/SHI_log/55758663/RP.*.dcm" --output /tmp/settling_test
      3. Check output files exist
      4. Verify CSV has is_settling column
    Expected Result: Analysis completes, all outputs generated
    Evidence: .sisyphus/evidence/task-08-g1-integration/

  Scenario: Compare statistics before/after settling filter
    Tool: Bash (python)
    Steps:
      1. Run with SETTLING_ENABLED=off, record mean_diff_x
      2. Run with SETTLING_ENABLED=on, record mean_diff_x
      3. assert mean_diff_x (on) < mean_diff_x (off)
    Expected Result: Settling filter reduces mean deviation
    Evidence: .sisyphus/evidence/task-08-comparison.txt
  ```

  **Commit**: NO
  - This is verification only, no code changes

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `python -m pytest tests/ -v` + `python -c "from src.calculator import calculate_differences_for_layer"`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, unused imports.
  Output: `Tests [N pass/N fail] | Import [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Data QA** — `unspecified-high`
  Run analysis on G1 data with SETTLING_ENABLED=on. Verify: (1) debug CSV has is_settling column, (2) statistics values changed, (3) no crashes.
  Output: `CSV [PASS/FAIL] | Statistics [CHANGED/UNCHANGED] | Crashes [NONE/N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec was built.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

- **1**: `feat(calculator): add settling detection configuration` — scv_init_G1.txt, scv_init_G2.txt, src/config_loader.py
- **2**: `feat(calculator): implement beam settling detection` — src/calculator.py, python -m pytest tests/test_calculator.py -k settling
- **3**: `feat(calculator): add is_settling flag to results` — src/calculator.py
- **4**: `feat(calculator): add is_settling column to debug CSV` — src/calculator.py
- **5-8**: `test(calculator): add settling detection tests` — tests/test_calculator.py, tests/test_config_loader.py

---

## Success Criteria

### Verification Commands
```bash
# All tests pass
python -m pytest tests/ -v

# Settling detection works
python -c "from src.calculator import calculate_differences_for_layer; print('OK')"

# Config loads correctly
python -c "from src.config_loader import parse_scv_init; c=parse_scv_init('scv_init_G1.txt'); print(c.get('SETTLING_ENABLED'))"

# Integration test
python main.py --log_dir /home/jokh38/MOQUI_SMC/data/SHI_log/55758663 --dcm_file /home/jokh38/MOQUI_SMC/data/SHI_log/55758663/RP.*.dcm --output /tmp/test_settling
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] Backward compatible (SETTLING_ENABLED=off behaves same as before)
- [ ] Debug CSV includes is_settling column
- [ ] Statistics exclude settling samples when enabled
