# Combined Case Report Design

## Goal

Allow one parent case directory containing multiple per-beam log subdirectories to generate a single combined PDF report covering all matched beams.

## Approved Design

- Treat a parent `--log_dir` as a case directory.
- If the directory contains `.ptn` files directly, preserve current behavior.
- If the directory contains subdirectories with `.ptn` files, treat each subdirectory as a delivery group and combine them into one report.
- Name the output PDF from the parent case directory basename, not a single beam subdirectory timestamp.
- Document the G1 case usage explicitly in `AGENTS.md`.

## Scope

- In scope: CLI/report naming behavior for case directories, documentation updates, and tests for combined-case naming.
- Out of scope: changing the internal matching strategy beyond existing delivery-group collection and beam matching.

## Notes

- `collect_ptn_delivery_groups()` already supports the required directory discovery pattern.
- The main code change is to derive a stable report name from the case root when the user points `--log_dir` at the parent sample directory.
