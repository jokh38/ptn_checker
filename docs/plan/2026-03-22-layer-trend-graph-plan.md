# Layer Trend Graph Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the summary-page layer trend chart with a combined horizontal X/Y mean±std error-bar plot.

**Architecture:** Keep the existing summary-page layout and data collection pipeline. Only change the middle-left trend panel rendering and add focused tests that assert the new axis orientation and plotted series labels.

**Tech Stack:** Python, matplotlib, unittest, numpy

---

### Task 1: Add a failing plot-level test

**Files:**
- Modify: `tests/test_report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Write the failing test**

Add a test that generates the summary page and asserts:
- the `Layer Trend` panel x-label is `Deviation (mm)`
- the y-label is `Layer`
- the legend includes `X mean ± std` and `Y mean ± std`

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_generator.py -k summary_page_uses_horizontal_xy_errorbar_trend -v`

Expected: FAIL because the current plot uses `Layer` on x-axis and radial metrics.

**Step 3: Write minimal implementation**

Update the trend panel in `src/report_generator.py` to render horizontal X/Y error bars with slight vertical offsets and reference lines.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report_generator.py -k summary_page_uses_horizontal_xy_errorbar_trend -v`

Expected: PASS

### Task 2: Run targeted regression checks

**Files:**
- Modify: `src/report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Run report generator tests**

Run: `python -m pytest tests/test_report_generator.py -v`

Expected: PASS

**Step 2: Review for summary-page regressions**

Confirm the existing summary-page and heatmap tests still pass and that the report PDF generation test remains green.
