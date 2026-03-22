# Heatmap Header Band Layout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the floating heatmap `X/Y` annotations with a dedicated header band so the top empty space becomes a structured header area.

**Architecture:** Keep the heatmap body and data unchanged, but add a small dedicated header axis above the heatmap body. Render `Mean | Std | Max | Mean | Std | Max` in the header row and center `X` and `Y` higher within the header band above their three-column groups.

**Tech Stack:** Python, matplotlib, unittest, numpy

---

### Task 1: Add a failing test for the dedicated header band

**Files:**
- Modify: `tests/test_report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Write the failing test**

Add a summary-page test that asserts a dedicated heatmap header axis exists and contains one `X` and one `Y`, separate from the heatmap body axis.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_generator.py -k header_band -v`

Expected: FAIL because the current implementation draws `X` and `Y` directly on the heatmap body axis.

**Step 3: Write minimal implementation**

Create a header-band axis above the heatmap body and move grouped label rendering into that axis.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report_generator.py -k header_band -v`

Expected: PASS

### Task 2: Run targeted regression checks

**Files:**
- Modify: `src/report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Run report generator tests**

Run: `python -m pytest tests/test_report_generator.py -v`

Expected: PASS
