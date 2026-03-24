# Redundancy Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the orphaned fluence-gamma stack and superseded report paths, then leave the repository aligned with the active `trajectory` and `point_gamma` workflow only.

**Architecture:** The cleanup keeps the current shipped path `main.py -> analysis_context -> calculator or point_gamma_workflow -> report_generator` and deletes code, tools, tests, and docs that only support the removed fluence-gamma/report-generator stacks. The active point-gamma/report path is then consolidated so only one summary implementation remains.

**Tech Stack:** Python, pytest, matplotlib, repository-wide static reference checks via `rg`

---

### Task 1: Remove the orphaned fluence-gamma code path

**Files:**
- Delete: `src/gamma_workflow.py`
- Delete: `src/gamma_analysis.py`
- Delete: `src/gamma_report_generator.py`
- Delete: `src/gamma_report_layout.py`
- Delete or trim: `src/fluence_map.py`
- Modify: `docs/REDUNDANCY_AUDIT_2026-03-24.md`

**Step 1: Confirm no active runtime imports remain**

Run: `rg -n "gamma_workflow|gamma_analysis|gamma_report_generator|gamma_report_layout|fluence_map" main.py src`
Expected: hits are only in isolated stacks and tests/tools

**Step 2: Remove the files and any dead imports**

Delete the orphaned fluence-gamma modules. If `src/fluence_map.py` is left with no remaining runtime or tool value after the agreed removal scope, delete it too.

**Step 3: Update audit note**

Record that the orphaned stack has been removed and note any intentionally retained pieces.

### Task 2: Remove superseded point-gamma/gamma report wrappers and unused summary implementation

**Files:**
- Delete: `src/point_gamma_report_generator.py`
- Modify: `src/point_gamma_report_layout.py`
- Modify: `src/report_generator.py`
- Modify: `src/report_layout.py` only if import cleanup is needed

**Step 1: Remove dead report-generator wrappers**

Delete `src/point_gamma_report_generator.py` and any imports/exports or tests that only exercise it.

**Step 2: Consolidate active point-gamma layout**

Remove the unused `generate_point_gamma_summary_page(...)` implementation from `src/point_gamma_report_layout.py` and keep only the active visual-page helper used by `src/report_generator.py`.

**Step 3: Clean imports**

Remove imports from `src/report_generator.py` and other modules that referenced deleted wrappers or superseded layout code.

### Task 3: Remove tools/docs/tests that only support removed stacks

**Files:**
- Delete: `tools/gamma_normalization_sweep.py`
- Delete: `tools/debug_fluence_export.py`
- Delete: `tests/test_gamma_workflow.py`
- Delete: `tests/test_gamma_analysis.py`
- Delete: `tests/test_fluence_map.py`
- Delete: `tests/test_gamma_report_generator.py`
- Delete: `tests/test_point_gamma_report_generator.py`
- Delete: `tests/test_debug_fluence_export.py`
- Delete: `tests/test_gamma_normalization_sweep.py`
- Delete: `gamma_evaluation.md`
- Delete: `docs/LOG_SPEC_DEVIATION.md`
- Modify: `README.md`

**Step 1: Remove tool/test/doc artifacts tied only to deleted stacks**

Delete the agreed non-runtime tools, their dedicated tests, and docs that only describe removed paths.

**Step 2: Update README**

Remove references to deleted tools/docs or removed fluence-gamma/report-generator stacks.

### Task 4: Simplify trivial wrappers and leftover redundancy

**Files:**
- Modify: `main.py`
- Modify: `src/analysis_context.py` only if needed

**Step 1: Remove the trivial `main.find_ptn_files()` wrapper**

Inline `src.ptn_discovery.find_ptn_files` usage directly where needed.

**Step 2: Do minimal follow-on cleanup**

Remove dead comments, imports, and stale references introduced by the deletions. Do not refactor active runtime logic beyond what is required to keep the repository coherent.

### Task 5: Verify the remaining supported workflow

**Files:**
- Test: `tests/test_main.py`
- Test: `tests/test_report_generator.py`
- Test: `tests/test_point_gamma_workflow.py`
- Test: `tests/test_config_loader.py`
- Test: `tests/test_analysis_context.py`

**Step 1: Run focused surviving tests**

Run:
`python -m pytest tests/test_main.py tests/test_report_generator.py tests/test_point_gamma_workflow.py tests/test_config_loader.py tests/test_analysis_context.py`

Expected: passing component-level verification for the remaining shipped workflow

**Step 2: Run one broader regression pass if the focused tests pass**

Run:
`python -m pytest`

Expected: the remaining suite passes after cleanup, or failures are clearly identified as fallout from deleted obsolete tests/files

**Step 3: Report validation scope**

Report results as `component validated` unless an actual sample-data app run is performed successfully end-to-end.

## Notes

- This plan is being executed in-place because the worktree prerequisite is unsafe in the current dirty repository state.
- The cleanup intentionally favors deletion over compatibility shims because the requested scope is “remove it all.”
