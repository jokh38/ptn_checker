# Heatmap Header Labels Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refine the summary-page heatmap labels to use horizontal metric headers, grouped X/Y direction labels, and abbreviated flag text in the Flag column.

**Architecture:** Keep the current vertical heatmap layout and right-side Flag column. Update `_draw_layer_heatmap` so metric tick labels show `Mean | Std | Max | Mean | Std | Max`, add grouped direction labels for `X` and `Y`, and expand flag text from one-letter codes to readable abbreviations.

**Tech Stack:** Python, matplotlib, numpy, unittest

---

### Task 1: Add failing presentation tests

**Files:**
- Modify: `tests/test_report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Write the failing tests**

Add assertions that:
- x-axis tick labels are horizontal and read `Mean`, `Std`, `Max`, `Mean`, `Std`, `Max`
- grouped `X` and `Y` direction labels are present
- flag text uses abbreviations like `FAIL`, `FB`, `NS`, `OV`

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_generator.py -k heatmap -v`

Expected: FAIL because the current renderer uses raw metric names, angled labels, and single-character flag codes.

**Step 3: Write minimal implementation**

Update `_draw_layer_heatmap` and `_layer_flag_codes` to render the approved label structure and flag abbreviations.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report_generator.py -k heatmap -v`

Expected: PASS

### Task 2: Run targeted regression checks

**Files:**
- Modify: `src/report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Run report generator tests**

Run: `python -m pytest tests/test_report_generator.py -v`

Expected: PASS
