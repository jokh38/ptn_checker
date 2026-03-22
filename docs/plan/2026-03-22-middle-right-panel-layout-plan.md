# Middle-Right Panel Layout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the summary-page middle-right panel into a four-row stack with top title, heatmap content, error-severity colorbar, and bottom FLAG abbreviation legend.

**Architecture:** Keep the heatmap body, header band, flag column, and colorbar logic, but move the `Layer Heatmap` title out of the heatmap axis into a dedicated top row and move the flag abbreviation legend into a dedicated bottom row spanning the panel width.

**Tech Stack:** Python, matplotlib, unittest, numpy

---

### Task 1: Add a failing layout-order test

**Files:**
- Modify: `tests/test_report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Write the failing test**

Add a summary-page test that asserts:
- the `Layer Heatmap` title is rendered in a dedicated axis above the heatmap body
- the flag legend axis is below the colorbar axis

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_generator.py -k middle_right_panel -v`

Expected: FAIL because the current title is still attached to the heatmap body axis and the legend is not the bottom row of the panel.

**Step 3: Write minimal implementation**

Refactor the middle-right gridspec into four rows and move the title and legend into their own axes.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report_generator.py -k middle_right_panel -v`

Expected: PASS

### Task 2: Run targeted regression checks

**Files:**
- Modify: `src/report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Run report generator tests**

Run: `python -m pytest tests/test_report_generator.py -v`

Expected: PASS
