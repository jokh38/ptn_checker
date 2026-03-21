# Post-Minimal-Dose Boundary Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a separate configurable 1 ms post-minimal-dose boundary window without changing the existing zero-dose boundary holdoff behavior.

**Architecture:** Extend zero-dose filter config with a new boundary duration, then apply a second carryover-marking pass in the calculator for treatment samples immediately following a minimal-dose spot. Preserve the existing `ZERO_DOSE_BOUNDARY_HOLDOFF_S` logic and combine both rules through the existing `sample_is_boundary_carryover` mask.

**Tech Stack:** Python, NumPy, pytest, YAML config parsing

---

### Task 1: Add failing config coverage

**Files:**
- Modify: `tests/test_config_loader.py`

**Step 1: Write the failing test**

Add assertions that YAML parsing exposes a new `ZERO_DOSE_POST_MINIMAL_DOSE_BOUNDARY_S` key and preserves the old `ZERO_DOSE_BOUNDARY_HOLDOFF_S`.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config_loader.py -q`
Expected: FAIL because the new config key is missing.

**Step 3: Write minimal implementation**

Update zero-dose config defaults, YAML parsing, and validation in `src/config_loader.py`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config_loader.py -q`
Expected: PASS.

### Task 2: Add failing calculator coverage

**Files:**
- Modify: `tests/test_calculator.py`

**Step 1: Write the failing test**

Add a test proving:
- existing `ZERO_DOSE_BOUNDARY_HOLDOFF_S` behavior remains unchanged,
- the new post-minimal-dose boundary marks samples from transit end through `< 1 ms`,
- those marked samples are excluded from filtered stats.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_calculator.py -q`
Expected: FAIL because the calculator does not yet read the new config key.

**Step 3: Write minimal implementation**

Add a second boundary-marking pass in `src/calculator.py` using the new config key and the existing spot-assignment semantics.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_calculator.py -q`
Expected: PASS.

### Task 3: Verify the integrated behavior

**Files:**
- Modify: `config.yaml`

**Step 1: Update default config**

Add `post_minimal_dose_boundary_s: 0.001` under `zero_dose_filter`.

**Step 2: Run focused verification**

Run: `python -m pytest tests/test_config_loader.py tests/test_calculator.py -q`
Expected: PASS.

**Step 3: Run broader regression check**

Run: `python -m pytest -q`
Expected: PASS or only pre-existing failures.
