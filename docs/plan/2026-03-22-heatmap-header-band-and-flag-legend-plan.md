# Heatmap Header Band And Flag Legend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the heatmap presentation by adding a dedicated grouped X/Y header band and an in-report legend explaining flag abbreviations.

**Architecture:** Keep the existing vertical heatmap and right-side Flag column. Extend `_draw_layer_heatmap` to render grouped direction labels in a dedicated header band above the heatmap and render a compact legend inside the Flag axis explaining `FAIL`, `FB`, `NS`, and `OV`.

**Tech Stack:** Python, matplotlib, unittest, numpy

---

### Task 1: Add failing tests for header band and flag legend

**Files:**
- Modify: `tests/test_report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Write the failing tests**

Add assertions that:
- the heatmap figure contains grouped `X` and `Y` header labels in a dedicated header area
- the Flag axis contains legend text explaining `FAIL`, `FB`, `NS`, and `OV`

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report_generator.py -k heatmap -v`

Expected: FAIL because the current renderer only draws loose `X/Y` text and no flag legend.

**Step 3: Write minimal implementation**

Update `_draw_layer_heatmap` to:
- draw a header band for grouped `X` and `Y`
- add compact legend text in the Flag area

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
