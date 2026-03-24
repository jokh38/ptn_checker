# Point Gamma Filtering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply the same settling and zero-dose sample exclusions used by trajectory analysis to `point_gamma` analysis before gamma evaluation.

**Architecture:** Reuse the existing sample-filtering semantics from `src/calculator.py` inside the active `src/point_gamma_workflow.py` path so both analysis modes exclude the same transient and zero-dose samples. Add focused workflow tests that prove settling and boundary/zero-dose exclusions reduce the evaluated gamma sample set in the intended cases.

**Tech Stack:** Python, NumPy, pytest/unittest

---

### Task 1: Add failing point-gamma filtering tests

**Files:**
- Modify: `tests/test_point_gamma_workflow.py`

**Step 1: Write the failing test**

Add tests that construct a small `plan_layer` and `log_data` where:
- initial samples are unsettled and should be excluded by settling detection
- a post-minimal-dose boundary sample should be excluded when zero-dose filtering is enabled

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_point_gamma_workflow.py -k "settling or zero_dose" -v`
Expected: FAIL because `calculate_point_gamma_for_layer(...)` still evaluates those samples.

**Step 3: Write minimal implementation**

Update the point-gamma workflow so it computes and applies the same analysis mask as trajectory mode before gamma evaluation.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_point_gamma_workflow.py -k "settling or zero_dose" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_point_gamma_workflow.py src/point_gamma_workflow.py src/calculator.py docs/plan/2026-03-24-point-gamma-filtering-plan.md
git commit -m "feat: apply settling and zero-dose filters to point gamma"
```

### Task 2: Refactor shared filtering logic

**Files:**
- Modify: `src/calculator.py`
- Modify: `src/point_gamma_workflow.py`

**Step 1: Extract reusable helpers**

Move or expose the minimal helper functions needed to build:
- settling mask
- assigned spot indices
- transit-min-dose sample mask
- boundary carryover sample mask

**Step 2: Run focused tests**

Run: `python -m pytest tests/test_point_gamma_workflow.py tests/test_calculator.py -v`
Expected: PASS

**Step 3: Keep output compatibility**

Ensure trajectory mode behavior stays unchanged and point-gamma mode still returns its existing keys while adding filtered sample counts only if needed.

### Task 3: Verify active analysis path

**Files:**
- Modify: `src/point_gamma_workflow.py`
- Test: `tests/test_main.py`

**Step 1: Confirm routing remains unchanged**

Keep `main.py` routing the `point_gamma` mode to `calculate_point_gamma_for_layer(...)`; only the internal sample selection should change.

**Step 2: Run verification**

Run: `python -m pytest tests/test_point_gamma_workflow.py tests/test_main.py tests/test_calculator.py -v`
Expected: PASS
