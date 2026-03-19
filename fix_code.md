# Code Review Report: PTN Checker

**Date:** 2026-03-19  
**Reviewer:** Atlas (Automated Code Review)

---

## Executive Summary

The codebase is generally well-structured with good documentation and test coverage. However, I identified several categories of issues ranging from minor inconsistencies to potential bugs and architectural improvements.

---

## 🔴 Critical Issues

### 1. Unused Imports in `main.py`

**File:** `main.py:7-8`

```python
import pydicom
import numpy as np
```

Both `pydicom` and `numpy` are imported at the top level but never used directly in `main.py`. They're used by the imported modules.

**Recommendation:** Remove unused imports to improve clarity.

```python
# Remove these lines:
# import pydicom
# import numpy as np
```

---

### 2. Variable Shadowing in `dicom_parser.py`

**File:** `src/dicom_parser.py:79-90`

```python
for i, beam in enumerate(plan.IonBeamSequence):
    ...
    for i in range(0, len(ion_control_points), 2):  # Shadows outer 'i'
```

The outer loop variable `i` is shadowed by the inner loop variable `i`. While this works, it makes debugging harder and can lead to confusion.

**Recommendation:** Rename the inner variable:

```python
for beam_idx, beam in enumerate(plan.IonBeamSequence):
    ...
    for cp_idx in range(0, len(ion_control_points), 2):
```

---

### 3. Missing `cumulative_mu` Key Validation in Calculator

**File:** `src/calculator.py:41-43`

The code checks for `cumulative_mu` but the plan layer might not have this key if `dicom_parser.py` fails to create it properly. The validation happens after accessing other keys.

**Current code:**
```python
for key in ('cumulative_mu', 'positions'):
    if key not in plan_layer:
        return {'error': f"Missing required plan_layer key: '{key}'"}
```

**Recommendation:** Consider adding validation that `cumulative_mu` is a non-empty array before the empty check on line 49.

---

## 🟠 Moderate Issues

### 4. Inconsistent Type Hints Usage

**Files:** Multiple

- `src/planrange_parser.py` uses modern type hints (`dict[str, LayerRangeInfo]`, `list[tuple[str, str]]`)
- `src/dicom_parser.py` uses legacy hints (`dict` without generics)
- `src/config_loader.py` has no return type hint
- `src/mu_correction.py` has partial type hints

**Recommendation:** Standardize on Python 3.9+ style type hints across all files, or use `from __future__ import annotations` for consistency.

```python
# Add to top of files if supporting Python 3.8:
from __future__ import annotations

# Then use consistent style:
def parse_scv_init(file_path: str) -> dict[str, float | str]:
    ...
```

---

### 5. Hardcoded Magic Numbers

**File:** `src/log_parser.py:115`

```python
beam_on_mask = beam_on_off_col > 2**15 + 2**14  # 49152
```

**File:** `src/log_parser.py:154-155`

```python
x_threshold = min(float(config_params.get('XTHRESHOLD', 60000)), 60000)
y_threshold = min(float(config_params.get('YTHRESHOLD', 60000)), 60000)
```

**Recommendation:** Define constants at module level:

```python
# Hardware constants
BEAM_ON_THRESHOLD = 2**15 + 2**14  # 49152 - bits 15 and 14 set
DEFAULT_POSITION_THRESHOLD = 60000

# Usage:
beam_on_mask = beam_on_off_col > BEAM_ON_THRESHOLD
x_threshold = min(float(config_params.get('XTHRESHOLD', DEFAULT_POSITION_THRESHOLD)), DEFAULT_POSITION_THRESHOLD)
```

---

### 6. Duplicated Gaussian Function

**Files:**
- `src/calculator.py:13-15` - `gaussian(x, amplitude, mean, stddev)`
- `src/report_generator.py:161-163` - `_gaussian(x, amplitude, mean, stddev)`

The same function is defined twice with slightly different formatting.

**Recommendation:** Extract to a shared `src/utils.py` or `src/math_utils.py` module:

```python
# src/utils.py
import numpy as np

def gaussian(x, amplitude, mean, stddev):
    """Gaussian function for curve fitting."""
    return amplitude * np.exp(-((x - mean) / stddev)**2 / 2)
```

---

### 7. Silent Data Loss in Position Filtering

**File:** `src/log_parser.py:151-175`

Position filtering happens twice (beam on/off, then position validity), but there's no logging of how many points were filtered out at each stage. This could mask data quality issues.

**Recommendation:** Add logging:

```python
# After beam on filtering
logger.debug(f"Beam on filter: kept {beam_on_mask.sum()} of {len(beam_on_mask)} points")

# After position validity filtering
logger.debug(f"Position validity filter: kept {pos_valid_mask.sum()} of {len(pos_valid_mask)} points")
```

---

### 8. Inconsistent Error Handling Strategy

**File:** `main.py:95-97`

```python
except (KeyError, ValueError, IOError) as e:
    logger.error(f"Error parsing PTN file {ptn_file}: {e}")
    continue
```

vs.

**File:** `main.py:121-123`

```python
except (KeyError, ValueError, TypeError) as e:
    logger.error(f"Error calculating differences for {beam_name}, Layer {layer_index}: {e}")
    continue
```

Different exception tuples are caught in similar contexts.

**Recommendation:** Standardize exception handling or document why different exceptions are caught.

---

### 9. Test Missing `FILTERED_BEAM_ON_OFF` Config Key

**File:** `tests/test_main.py:53-59` and `tests/test_calculator.py:32-36`

Test configs don't include `FILTERED_BEAM_ON_OFF`, relying on the default `'on'`. This could mask bugs if the default changes.

**Recommendation:** Explicitly set `FILTERED_BEAM_ON_OFF` in test configs:

```python
self.config = {
    'XPOSGAIN': 1.0, 'YPOSGAIN': 1.0,
    'XPOSOFFSET': 0.0, 'YPOSOFFSET': 0.0,
    'TIMEGAIN': 0.001,
    'FILTERED_BEAM_ON_OFF': 'on'  # Explicit for clarity
}
```

---

## 🟡 Minor Issues / Style

### 10. Commented-Out Code

**File:** `main.py:88`

```python
# print(f"Processing {beam_name}, Layer {layer_index} with {os.path.basename(ptn_file)}")
```

**Recommendation:** Remove or convert to proper debug logging:

```python
logger.debug(f"Processing {beam_name}, Layer {layer_index} with {os.path.basename(ptn_file)}")
```

---

### 11. Debug Flag Pattern Could Be Improved

**File:** `main.py:79, 107-120`

The `debug_csv_saved` flag pattern is a bit awkward. Consider using a counter or more explicit control.

**Current:**
```python
debug_csv_saved = False
...
save_csv_for_this_layer = not debug_csv_saved
if save_csv_for_this_layer:
    debug_csv_saved = True
```

**Alternative (if you want first N layers):**
```python
debug_csv_count = 0
max_debug_csvs = 1
...
if debug_csv_count < max_debug_csvs:
    save_csv_for_this_layer = True
    debug_csv_count += 1
```

---

### 12. Missing Docstrings

Some functions have minimal or missing docstrings:

- `src/config_loader.py`: Missing return type details in docstring
- Consider adding parameter descriptions to all public functions

---

### 13. Implicit Mutation in Return Type

**File:** `src/mu_correction.py:107-134`

The function modifies `log_data` in place AND returns it. This is inconsistent.

**Current:**
```python
def apply_mu_correction(...) -> dict:
    ...
    log_data['mu'] = np.cumsum(corrected).astype(np.float32)
    return log_data  # Returns modified input
```

**Recommendation:** Be explicit about mutation pattern:

**Option A (in-place, no return):**
```python
def apply_mu_correction(...) -> None:
    """Modifies log_data in place."""
    log_data['mu'] = np.cumsum(corrected).astype(np.float32)
```

**Option B (functional, return new):**
```python
def apply_mu_correction(...) -> dict:
    """Returns a new dict with corrected MU values."""
    result = log_data.copy()
    result['mu'] = np.cumsum(corrected).astype(np.float32)
    return result
```

---

### 14. README Inconsistency

**File:** `README.md`

The README mentions `scv_init_G1.txt` and `scv_init_G2.txt` as required config files, but these files are not in the repository (may be in `.gitignore`).

**Recommendation:** Either:
- Add example config files to the repo (e.g., `scv_init_EXAMPLE.txt`)
- Update README to note these must be created by the user

---

### 15. Missing `requirements.txt`

The README mentions creating a `requirements.txt` but none exists in the repository.

**Recommendation:** Add `requirements.txt`:

```
numpy>=1.20.0
scipy>=1.7.0
matplotlib>=3.4.0
pydicom>=2.2.0
pytest>=6.0.0
```

Or use `pyproject.toml` for modern Python packaging.

---

## 🔵 Potential Improvements

### 16. Consider Using `pathlib`

Current code uses `os.path` extensively. `pathlib` provides cleaner, more readable path operations.

**Example transformation:**

```python
# Current
config_path = os.path.join(os.path.dirname(__file__) or '.', config_file)

# With pathlib
from pathlib import Path
config_path = Path(__file__).parent / config_file
```

---

### 17. Add `__all__` to Modules

For explicit public API definition, add `__all__` lists to each module:

```python
# src/calculator.py
__all__ = ['calculate_differences_for_layer', 'gaussian']
```

---

### 18. Consider Logging Configuration Externalization

**File:** `main.py:146`

```python
logging.basicConfig(level=logging.INFO)
```

Hardcoded logging level.

**Recommendation:** Make this configurable via command-line argument:

```python
parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    default="INFO", help="Set logging level")
...
logging.basicConfig(level=getattr(logging, args.log_level))
```

---

### 19. Empty `src/__init__.py`

The package init file is empty. Consider adding version info or public exports:

```python
# src/__init__.py
"""PTN Checker - Radiotherapy Plan and Log File Analyzer."""

__version__ = "1.0.0"
__all__ = ['dicom_parser', 'log_parser', 'calculator', 'report_generator', 
           'config_loader', 'planrange_parser', 'mu_correction']
```

---

### 20. Test Class Naming Inconsistency

- `TestMain` (test_main.py)
- `TestCalculator` (test_calculator.py)
- `TestCorrectLogParser` (test_log_parser.py) - "Correct" prefix is unusual

**Recommendation:** Rename `TestCorrectLogParser` to `TestLogParser`.

---

## Summary Table

| Severity | Count | Examples |
|----------|-------|----------|
| 🔴 Critical | 3 | Unused imports, variable shadowing, validation gaps |
| 🟠 Moderate | 6 | Type hints, magic numbers, duplicated code |
| 🟡 Minor | 8 | Commented code, docstrings, README issues |
| 🔵 Improvement | 4 | pathlib, `__all__`, logging config |

---

## Recommended Priority Order

| Priority | Issue | File | Effort |
|----------|-------|------|--------|
| 1 | Fix variable shadowing | `dicom_parser.py` | Low |
| 2 | Remove unused imports | `main.py` | Low |
| 3 | Add `requirements.txt` | Root | Low |
| 4 | Standardize type hints | Multiple | Medium |
| 5 | Extract duplicated Gaussian function | New file | Low |
| 6 | Add logging for data filtering | `log_parser.py` | Low |
| 7 | Add `FILTERED_BEAM_ON_OFF` to test configs | `tests/*.py` | Low |
| 8 | Convert commented code to debug logging | `main.py` | Low |
| 9 | Define constants for magic numbers | `log_parser.py` | Low |
| 10 | Add example config file | Root | Low |

---

## Files to Modify

```
main.py                    # Remove unused imports, fix commented code
src/dicom_parser.py        # Fix variable shadowing
src/log_parser.py          # Add constants, add logging
src/calculator.py          # Move gaussian to shared util
src/report_generator.py    # Import gaussian from shared util
src/config_loader.py       # Add type hints
src/__init__.py            # Add version/exports
tests/test_main.py         # Add explicit config key
tests/test_calculator.py   # Add explicit config key
tests/test_log_parser.py   # Rename class
requirements.txt           # Create new file
```
