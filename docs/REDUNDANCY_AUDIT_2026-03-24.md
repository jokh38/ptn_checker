# Redundancy Audit

Date: 2026-03-24

Validation status: `component validated`

This note records redundancy and likely-unnecessary-file candidates verified by static call-path tracing, repository reference scans, and targeted tests. It does not claim end-to-end validation.

## Cleanup Status

Removed orphaned fluence-gamma and superseded report-stack files:

- [src/gamma_workflow.py](/home/jokh38/MOQUI_SMC/ptn_checker/src/gamma_workflow.py)
- [src/gamma_analysis.py](/home/jokh38/MOQUI_SMC/ptn_checker/src/gamma_analysis.py)
- [src/gamma_report_generator.py](/home/jokh38/MOQUI_SMC/ptn_checker/src/gamma_report_generator.py)
- [src/gamma_report_layout.py](/home/jokh38/MOQUI_SMC/ptn_checker/src/gamma_report_layout.py)
- [src/fluence_map.py](/home/jokh38/MOQUI_SMC/ptn_checker/src/fluence_map.py)
- [src/point_gamma_report_generator.py](/home/jokh38/MOQUI_SMC/ptn_checker/src/point_gamma_report_generator.py)

Removed obsolete tools/tests/docs tied only to those stacks:

- [tools/gamma_normalization_sweep.py](/home/jokh38/MOQUI_SMC/ptn_checker/tools/gamma_normalization_sweep.py)
- [tools/debug_fluence_export.py](/home/jokh38/MOQUI_SMC/ptn_checker/tools/debug_fluence_export.py)
- [tests/test_gamma_workflow.py](/home/jokh38/MOQUI_SMC/ptn_checker/tests/test_gamma_workflow.py)
- [tests/test_gamma_analysis.py](/home/jokh38/MOQUI_SMC/ptn_checker/tests/test_gamma_analysis.py)
- [tests/test_fluence_map.py](/home/jokh38/MOQUI_SMC/ptn_checker/tests/test_fluence_map.py)
- [tests/test_gamma_report_generator.py](/home/jokh38/MOQUI_SMC/ptn_checker/tests/test_gamma_report_generator.py)
- [tests/test_point_gamma_report_generator.py](/home/jokh38/MOQUI_SMC/ptn_checker/tests/test_point_gamma_report_generator.py)
- [tests/test_debug_fluence_export.py](/home/jokh38/MOQUI_SMC/ptn_checker/tests/test_debug_fluence_export.py)
- [tests/test_gamma_normalization_sweep.py](/home/jokh38/MOQUI_SMC/ptn_checker/tests/test_gamma_normalization_sweep.py)
- [gamma_evaluation.md](/home/jokh38/MOQUI_SMC/ptn_checker/gamma_evaluation.md)
- [docs/LOG_SPEC_DEVIATION.md](/home/jokh38/MOQUI_SMC/ptn_checker/docs/LOG_SPEC_DEVIATION.md)

Current runtime path still verified:

- `main.py` -> `analysis_context` -> `calculator` or `point_gamma_workflow` -> `report_generator`
- `src/point_gamma_report_layout.py` is retained only for `generate_point_gamma_visual_page(...)`

Known gaps:

- This note remains `component validated`; no end-to-end app run was performed in this task.
- The repository still has unrelated pre-existing dirty-tree changes outside this cleanup.
