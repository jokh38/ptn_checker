# Code Review Findings: PTN Checker

## Overview
This document reflects the current repository state after validating each finding against the codebase. Validation scope: `component validated`. It separates verified observations from recommendations and avoids treating style preferences as defects.

---

## 1. VERIFIED DUPLICATION AND STRUCTURE FINDINGS

### 1.1 Duplicated Helper: `find_ptn_files()`
| File | Lines | Notes |
|------|-------|-------|
| `main.py:29-35` | 7 lines | Returns unsorted list |
| `layer_normalization_values.py:14-20` | 7 lines | Returns sorted list |

Observation: These functions duplicate the same filesystem walk logic, but they are not exact duplicates because the return ordering differs.

Recommendation: Extract a shared helper only if both call sites can agree on ordering semantics.

### 1.2 Near-Duplicate Workflow: `run_analysis()`
| File | Lines | Purpose |
|------|-------|---------|
| `main.py:137-325` | 189 lines | Main PDF/CSV analysis pipeline with delivery-group matching |
| `layer_normalization_values.py:184-234` | 51 lines | MU normalization CSV pipeline |

Observation: Both flows share the same broad sequence of steps:
Parse DICOM -> load machine/config data -> find PTN files -> parse PlanRange -> apply MU correction.

Caveat: The current `main.py` pipeline has materially diverged from the CSV-only workflow because it now collects delivery groups and matches them to beams before iterating layers.

Recommendation: Consider extracting shared loading/matching steps if this logic continues to evolve in both places.

### 1.3 Repetitive Array Handling in `log_parser.py`
Observation: [src/log_parser.py](/home/jokh38/MOQUI_SMC/ptn_checker/src/log_parser.py#L117) and [src/log_parser.py](/home/jokh38/MOQUI_SMC/ptn_checker/src/log_parser.py#L187) contain repetitive per-array update blocks. They are not identical:
- The first block applies a boolean mask.
- The second block slices away leading outlier samples.

Recommendation: A helper may still help readability, but it should support both mask-based and slice-based filtering instead of assuming a single `_apply_mask_to_all_arrays(mask)` shape.

---

## 2. VERIFIED CODE QUALITY OBSERVATIONS

### 2.1 Large Functions
| Function | File | Lines | Severity |
|----------|------|-------|----------|
| `_generate_summary_page()` | `src/report_generator.py:611` | **457** | CRITICAL |
| `calculate_differences_for_layer()` | `src/calculator.py:120` | **314** | CRITICAL |
| `parse_ptn_file()` | `src/log_parser.py:4` | **245** | CRITICAL |
| `_generate_executive_summary()` | `src/report_generator.py:1029` | **151** | HIGH |
| `_draw_layer_heatmap()` | `src/report_generator.py:460` | **149** | HIGH |
| `_draw_filter_panel()` | `src/report_generator.py:209` | **126** | HIGH |
| `parse_dcm_file()` | `src/dicom_parser.py:153` | **114** | MEDIUM |
| `generate_report()` | `src/report_generator.py:1223` | **101** | MEDIUM |

Observation: These counts were validated from the current AST spans in the repository.

### 2.2 Functions With High Parameter Counts
| Function | Parameters | File |
|----------|------------|------|
| `_draw_layer_heatmap()` | **11** | `src/report_generator.py:475` |
| `_draw_layer_table()` | 9 | `src/report_generator.py:391` |
| `_detect_settling()` | 8 | `src/calculator.py:23` |
| `_build_layer_row()` | 6 | `src/report_csv_exporter.py:65` |

Observation: These counts are accurate. Whether they are too many is a design judgment, but they are legitimate refactoring candidates.

### 2.3 Large Module: `report_generator.py`
- `src/report_generator.py` is **1323 lines**
- It currently owns plotting, layout, PDF composition, metric display, and pass/fail presentation logic

Observation: This is a valid maintainability concern, though "god module" is a characterization rather than an objective defect.

### 2.4 Deep Nesting
- Nested control flow is present in several files
- Confirmed examples include:
  - `src/calculator.py:246-263`
  - `src/dicom_parser.py:113-144`

Observation: The previously reported aggregate number of deeply nested lines was not independently reproduced, so this section keeps only the verified examples.

---

## 3. MODULE ORGANIZATION FINDINGS

### 3.1 Root-Level `layer_normalization_values.py`
- `layer_normalization_values.py` is 270 lines and lives at the repository root
- Its test imports it directly with `import layer_normalization_values`

Observation: The file location is unusual relative to the rest of `src/`, but the current test setup does not expect `src.`-style imports for this module.

Recommendation: Move it into `src/` only if you also want to standardize packaging/import conventions.

### 3.2 Empty `src/__init__.py`
- `src/__init__.py` is empty

Observation: This is factually true, but not automatically a defect. It only matters if the project wants a curated package-level public API.

### 3.3 Missing Dedicated Test Module
- There is no `tests/test_report_csv_exporter.py`

Observation: Coverage may still exist indirectly through higher-level tests, but there is no dedicated test file for this module.

Additional observation: combined multi-delivery report behavior still lacks direct test coverage. The current main-path naming test only checks basename-derived report naming, not multi-group report generation behavior.

### 3.4 Private Function Imports
- `src/report_csv_exporter.py` imports private functions from `src/report_generator.py`:
  - `_layer_passes`
  - `_metric_value`
  - `_spot_pass_summary`

Observation: This coupling is real and increases the chance that report-generator internals will become de facto shared API.

---

## 4. HARDCODED VALUES AND TUNABLE CONSTANTS

### Verified Constants
| Value | Location | Current |
|-------|----------|---------|
| `dose_dividing_factor` default | `src/mu_correction.py:112` | `10.0` |
| `MAX_SPEED` | `src/plan_timing.py:7` | `2000.0` |
| `MIN_DOSERATE` | `src/plan_timing.py:8` | `1.4` |
| `ALIGNMENT_TOLERANCE_MM` | `src/log_parser.py:155` | `1.0` |
| Figure size constants | `src/report_generator.py:11-12` | Module-level |
| Threshold constants | `src/report_generator.py:15-19` | Module-level |

Observation: These values are present and hardcoded. Whether they should be configurable depends on expected deployment variability and how often they change.

---

## 5. MISSING DOCSTRINGS

| Function | File |
|----------|------|
| `parse_app_config()` | `src/config_loader.py:129` |
| `parse_yaml_config()` | `src/config_loader.py:139` |
| `load_doserate_table()` | `src/plan_timing.py:17` |
| `get_doserate_for_energy()` | `src/plan_timing.py:27` |
| `build_layer_time_trajectory()` | `src/plan_timing.py:38` |
| `export_report_csv()` | `src/report_csv_exporter.py:110` |

Observation: These public functions currently have no docstrings. This list is exhaustive for the current public functions in `src/` that are missing docstrings.

---

## 6. POSITIVE FINDINGS AND ASSESSMENTS

Verified observations:
- No circular dependencies were found in the current `src` import graph.
- No `TODO` markers were found in the searched source/test files.

Assessments:
- Naming is broadly consistent with Python conventions.
- The repository has a substantial automated test suite.
- Most `src` modules have limited direct dependencies on other project modules.

Note: The earlier claim that there were no `print()` statements was incorrect. `layer_normalization_values.py` contains CLI `print()` calls when reporting output file paths.

---

## 7. PRIORITIZED ACTION PLAN

### IMMEDIATE
1. Correct factual inaccuracies in this review document before using it for planning.
2. Add a focused test module for `src/report_csv_exporter.py`.
3. Add direct coverage for combined multi-delivery report behavior instead of relying on the current basename-only naming test.
4. Decide whether `layer_normalization_values.py` should remain a top-level CLI script or become part of the `src` package.

### HIGH
5. Remove or reduce private cross-module imports by extracting shared report helpers into a neutral module.
6. Add docstrings to public functions listed above.
7. Refactor the largest functions in `report_generator.py`, `calculator.py`, and `log_parser.py`.

### MEDIUM
8. Consolidate duplicated PTN-discovery and analysis-loading logic where behavior truly matches.
9. Revisit hardcoded thresholds/constants and promote only the ones that need runtime configurability.
10. Break `report_generator.py` into smaller modules if ongoing feature work continues there.

### LOW
11. Standardize package exports in `src/__init__.py` if a package-level API becomes useful.
12. Reduce repetitive array-handling code in `log_parser.py` with a helper that supports both masking and slicing.
