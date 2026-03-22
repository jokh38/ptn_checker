# Layer Heatmap Flag Column Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert the summary-page layer heatmap to a vertical layout and replace the separate flag strip with a rightmost single-character `Flag` column.

**Architecture:** Keep the summary-page split layout and reuse the per-layer metrics already collected in `src/report_generator.py`. Update `_draw_layer_heatmap` so the main heatmap uses `y=layer` and `x=metric`, and render a narrow companion axis as a visual `Flag` column with one prioritized single-character code per layer.

**Tech Stack:** Python, matplotlib, numpy, unittest

---

### Task 1: Add failing tests for the new heatmap layout

**Files:**
- Modify: `tests/test_report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Write the failing tests**

Add coverage that asserts:
- the main heatmap array is transposed to layer-by-metric shape
- the main heatmap x-label is `Metric`
- the main heatmap y-label is `Layer`
- the flag column contains one row per layer and one column
- the flag column renders single-character texts using the `F > N > O > B` priority

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_report_generator.py -k heatmap -v`

Expected: FAIL because the current heatmap uses `x=layer`, `y=metric`, and a bottom flag strip.

**Step 3: Write minimal implementation**

Update `_draw_layer_heatmap` and the summary-page layout to:
- transpose the heatmap
- create a narrow right-side flag axis
- render single-character flag cells and remove the separate bottom flag strip

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_report_generator.py -k heatmap -v`

Expected: PASS

### Task 2: Run targeted regression checks

**Files:**
- Modify: `src/report_generator.py`
- Test: `tests/test_report_generator.py`

**Step 1: Run report generator tests**

Run: `python -m pytest tests/test_report_generator.py -v`

Expected: PASS
