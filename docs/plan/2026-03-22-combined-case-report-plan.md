# Combined Case Report Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate one PDF for a multi-subdirectory case such as G1 and document that usage in the runbook.

**Architecture:** Reuse the existing multi-group PTN collection logic in `main.py`. Add a small report-name derivation helper so a parent case directory produces a single case-level PDF name, then document the parent-directory invocation in `AGENTS.md`.

**Tech Stack:** Python, unittest, argparse, markdown

---

### Task 1: Add a failing test for case-level report naming

**Files:**
- Modify: `tests/test_main.py`
- Test: `tests/test_main.py`

**Step 1: Write the failing test**

Add a test that patches `sys.argv` with a parent case directory path and asserts `main.generate_report` is called with `report_name` equal to `<case_id>_<today>`.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main.py -k case_directory -v`

Expected: FAIL because current behavior derives the report name from the provided directory basename without explicit case-directory intent coverage.

**Step 3: Write minimal implementation**

Add a helper in `main.py` to derive the report base name from the case directory and use it from `main()`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_main.py -k case_directory -v`

Expected: PASS

### Task 2: Update AGENTS.md for combined-case usage

**Files:**
- Modify: `AGENTS.md`

**Step 1: Add G1 parent-directory example**

Document that:
- `G1` can be run by pointing `--log_dir` at `/home/jokh38/MOQUI_SMC/data/SHI_log/55758663`
- one combined PDF is produced for all matched beam subdirectories
- outputs should be written under `/output/55758663`

### Task 3: Run targeted regression checks

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`
- Modify: `AGENTS.md`

**Step 1: Run targeted tests**

Run: `python -m pytest tests/test_main.py -v`

Expected: PASS

**Step 2: Run the G1 case from the parent directory**

Run: `python main.py --log_dir /home/jokh38/MOQUI_SMC/data/SHI_log/55758663 --dcm_file /home/jokh38/MOQUI_SMC/data/SHI_log/55758663/RP.1.2.840.113854.116162735116359465886295179291233309871.1.dcm --output /home/jokh38/MOQUI_SMC/ptn_checker/output/55758663`

Expected: one combined PDF named `55758663_<date>.pdf`
