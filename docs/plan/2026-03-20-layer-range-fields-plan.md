# Layer Range Fields Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-layer dose monitor range fields to the normalization CSV, including plan-vs-log and dose1-vs-dose2 difference markers.

**Architecture:** Extend the PlanRange parser so each PTN layer lookup carries all range columns needed by reporting. Keep MU correction based on `DOSE1_RANGE`, and update `layer_normalization_values.py` to emit the three requested CSV fields from parsed PlanRange data.

**Tech Stack:** Python, `csv`, `unittest`, `unittest.mock`

---

### Task 1: Add failing coverage for new layer CSV fields

**Files:**
- Modify: `tests/test_layer_normalization_values.py`
- Test: `tests/test_layer_normalization_values.py`

**Step 1: Write the failing test**

Add assertions that the layer CSV contains:
- `DOSE1_RANGE`
- `RANGE_PLAN_LOG_DIFF`
- `RANGE_1_2_DIFF`

Cover one row where plan/log range differs and dose1/dose2 differs, and one row where they match.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_layer_normalization_values.py -v`

Expected: FAIL because the CSV does not yet include the new fields.

### Task 2: Parse the extra PlanRange values

**Files:**
- Modify: `src/planrange_parser.py`
- Test: `tests/test_layer_normalization_values.py`

**Step 1: Write minimal implementation**

Extend `LayerRangeInfo` to carry:
- `dose1_range_code`
- `dose2_range_code`
- `plan_dose1_range_code`
- `plan_dose2_range_code`

Parse them from PlanRange row columns 5-8 while preserving the existing lookup shape and MU-correction inputs.

**Step 2: Run focused tests**

Run: `python -m pytest tests/test_layer_normalization_values.py -v`

Expected: still FAIL until CSV writing is updated.

### Task 3: Emit the new CSV fields from layer normalization analysis

**Files:**
- Modify: `layer_normalization_values.py`
- Test: `tests/test_layer_normalization_values.py`

**Step 1: Write minimal implementation**

Populate per-layer rows with:
- `DOSE1_RANGE`
- `RANGE_PLAN_LOG_DIFF`
- `RANGE_1_2_DIFF`

Rules:
- `DOSE1_RANGE` records the log-side `DOSE1_RANGE`
- `RANGE_PLAN_LOG_DIFF` records whether `PLAN_DOSE1_RANGE` and `DOSE1_RANGE` differ
- `RANGE_1_2_DIFF` records whether `DOSE1_RANGE` and `DOSE2_RANGE` differ

Use concise string markers only when a difference exists; otherwise leave the field empty.

**Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_layer_normalization_values.py -v`

Expected: PASS

### Task 4: Run broader verification

**Files:**
- Modify: `src/planrange_parser.py`
- Modify: `layer_normalization_values.py`
- Modify: `tests/test_layer_normalization_values.py`

**Step 1: Run relevant tests**

Run: `python -m pytest tests/test_layer_normalization_values.py tests/test_main.py -v`

Expected: PASS or unrelated failures documented.
