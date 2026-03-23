"""
MU correction logic adapted from mqi_interpreter.

Applies energy-dependent interpolation corrections, monitor range scaling,
and a dose dividing factor to convert raw dose1_au counts into physically
corrected MU values.
"""

import logging

import numpy as np
from scipy.interpolate import PchipInterpolator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Correction data constants (from mqi_interpreter/processing/interpolation.py)
# ---------------------------------------------------------------------------
PROTON_PER_DOSE_ENERGY_RANGE = np.array([
    70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230
], dtype=np.float32)

PROTON_PER_DOSE_CORRECTION_FACTORS = np.array([
    1.0, 1.12573609032495, 1.25147616113001, 1.36888442326936, 1.48668286253201,
    1.60497205195899, 1.71741194754422, 1.82898327045955, 1.94071715123743,
    2.04829230739643, 2.16168786761159, 2.27629228444253, 2.39246901674031,
    2.50561983301185, 2.63593473689952, 2.75663921459094, 2.89392497566575
], dtype=np.float32)

DOSE_PER_MU_COUNT_ENERGY_RANGE = np.array([
    70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230
], dtype=np.float32)

DOSE_PER_MU_COUNT_CORRECTION_FACTORS = np.array([
    1.0, 0.989255716854649, 0.973421729297953, 0.967281770613755, 0.958215625815887,
    0.946937840980162, 0.942685675037711, 0.940168906626851, 0.931161417057087,
    0.918762676945622, 0.904569498824145, 0.888164591949398, 0.876689052268837,
    0.872826195199581, 0.871540965585644, 0.859481169160383, 0.8524232713089
], dtype=np.float32)


# ---------------------------------------------------------------------------
# PCHIP interpolator with constant extrapolation outside [70, 230] MeV
# ---------------------------------------------------------------------------
class ConstExtrapPchipInterpolator:
    """PCHIP interpolator that uses boundary values for out-of-range inputs."""

    def __init__(self, x, y):
        x = np.asarray(x, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32)
        sort_idx = np.argsort(x)
        self._x = x[sort_idx]
        self._y = y[sort_idx]
        self._interpolator = PchipInterpolator(self._x, self._y, extrapolate=False)
        self._min_x, self._max_x = self._x[0], self._x[-1]
        self._min_y, self._max_y = self._y[0], self._y[-1]

    def __call__(self, xi):
        xi = np.asarray(xi)
        yi = np.empty_like(xi, dtype=np.float32)

        within = (xi >= self._min_x) & (xi <= self._max_x)
        if np.any(within):
            yi[within] = self._interpolator(xi[within])
        below = xi < self._min_x
        if np.any(below):
            yi[below] = self._min_y
        above = xi > self._max_x
        if np.any(above):
            yi[above] = self._max_y

        return yi.item() if xi.ndim == 0 else yi


# Module-level interpolator instances
PROTON_DOSE_INTERPOLATOR = ConstExtrapPchipInterpolator(
    PROTON_PER_DOSE_ENERGY_RANGE, PROTON_PER_DOSE_CORRECTION_FACTORS
)
MU_COUNT_DOSE_INTERPOLATOR = ConstExtrapPchipInterpolator(
    DOSE_PER_MU_COUNT_ENERGY_RANGE, DOSE_PER_MU_COUNT_CORRECTION_FACTORS
)


# ---------------------------------------------------------------------------
# Monitor range factor (from mqi_interpreter/generators/moqui_generator.py)
# ---------------------------------------------------------------------------
def get_monitor_range_factor(monitor_range_code: int) -> float:
    """Return the monitor range scaling factor for the given code."""
    factors = {
        1: 160.0 / 470.0,
        2: 1.0,
        3: 2.978723404255319,
        4: 8.936170212765957,
        5: 26.80851063829787,
    }
    if monitor_range_code not in factors:
        logger.warning(
            "Unrecognized monitor_range_code %d, defaulting factor to 1.0",
            monitor_range_code,
        )
        return 1.0
    return factors[monitor_range_code]


# ---------------------------------------------------------------------------
# Convenience function to apply all corrections to parsed PTN log data
# ---------------------------------------------------------------------------
def apply_mu_correction(
    log_data: dict,
    nominal_energy: float,
    monitor_range_code: int,
    dose_dividing_factor: float = 10.0,
) -> dict:
    """
    Replace ``log_data['mu']`` with physics-corrected cumulative MU.

    The correction chain (matching mqi_interpreter logic) is::

        corrected = dose1_au
                    * proton_per_dose_factor(energy)
                    * dose_per_mu_count_factor(energy)
                    * monitor_range_factor(code)
                    / dose_dividing_factor

    Unlike mqi_interpreter (which rounds to int for MOQUI CSV output),
    we keep float values because ptn_checker uses MU for continuous
    interpolation.
    """
    corrected = log_data['dose1_au'].astype(np.float64)
    corrected *= PROTON_DOSE_INTERPOLATOR(nominal_energy)
    corrected *= MU_COUNT_DOSE_INTERPOLATOR(nominal_energy)
    corrected *= get_monitor_range_factor(monitor_range_code)
    corrected /= dose_dividing_factor
    log_data['mu_per_sample_corrected'] = corrected.astype(np.float32)
    log_data['mu'] = np.cumsum(corrected).astype(np.float32)
    return log_data
