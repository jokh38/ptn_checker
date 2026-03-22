# Review Followups Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the remaining actionable items from `code-review-findings.md` without regressing current behavior.

**Architecture:** Extract shared helpers where behavior already matches, keep existing entrypoints stable for tests and CLI use, and split the largest functions into smaller internal helpers before changing higher-level module boundaries. Update the review document last so it reflects the final code state rather than an intermediate snapshot.

**Tech Stack:** Python, NumPy, SciPy, Matplotlib, pydicom, pytest

---

### Task 1: Refactor Parsing And Analysis Helpers

**Files:**
- Modify: `src/log_parser.py`
- Modify: `src/dicom_parser.py`
- Modify: `src/calculator.py`
- Create: `src/analysis_context.py`
- Test: `tests/test_log_parser.py`
- Test: `tests/test_dicom_parser.py`
- Test: `tests/test_calculator.py`

**Step 1: Add or extend focused tests**

- Add tests that cover helper-preserved behavior in PTN filtering, DICOM layer extraction, and layer-analysis result fields.

**Step 2: Run targeted tests to verify the baseline**

Run: `python -m pytest tests/test_log_parser.py tests/test_dicom_parser.py tests/test_calculator.py -q`

**Step 3: Extract minimal helpers**

- In `src/log_parser.py`, introduce reusable array-application helpers for mask and prefix-slice operations.
- In `src/dicom_parser.py`, extract beam/layer parsing helpers and zero-dose classifier config mapping.
- In `src/calculator.py`, extract validation, interpolation, zero-dose filtering, histogram fitting, and result-assembly helpers.
- In `src/analysis_context.py`, centralize shared DICOM/config/PTN-loading steps used by both entrypoints where semantics already match.

**Step 4: Re-run targeted tests**

Run: `python -m pytest tests/test_log_parser.py tests/test_dicom_parser.py tests/test_calculator.py tests/test_main.py tests/test_layer_normalization_values.py -q`

### Task 2: Decompose Report Generation And Package Layout

**Files:**
- Modify: `src/report_generator.py`
- Create: `src/report_layout.py`
- Create: `src/layer_normalization_values.py`
- Modify: `layer_normalization_values.py`
- Modify: `src/__init__.py`
- Test: `tests/test_report_generator.py`
- Test: `tests/test_layer_normalization_values.py`

**Step 1: Add or extend tests**

- Keep current public imports stable while allowing internal implementation moves.
- Add assertions if needed for wrapper imports or stable CLI behavior.

**Step 2: Run targeted tests to confirm the starting point**

Run: `python -m pytest tests/test_report_generator.py tests/test_layer_normalization_values.py -q`

**Step 3: Extract report helpers and packaging wrappers**

- Move heatmap/summary/executive-summary helper logic into `src/report_layout.py` where it reduces `src/report_generator.py` size without breaking tests.
- Keep `src/report_generator.py` as the stable import surface used by the rest of the codebase and tests.
- Move the normalization implementation into `src/layer_normalization_values.py`.
- Turn the repository-root `layer_normalization_values.py` into a thin compatibility CLI/import wrapper.
- Add curated exports in `src/__init__.py` that match actual project entrypoints.

**Step 4: Re-run targeted tests**

Run: `python -m pytest tests/test_report_generator.py tests/test_layer_normalization_values.py tests/test_main.py -q`

### Task 3: Update Review Document And Validate Repository

**Files:**
- Modify: `code-review-findings.md`

**Step 1: Update the review document**

- Correct findings that are no longer true.
- Record implementation decisions instead of stale recommendations where the code now reflects a chosen direction.
- Preserve explicit separation of observations versus assumptions.

**Step 2: Run full verification**

Run: `python -m pytest -q`

