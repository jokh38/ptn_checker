from functools import lru_cache
from pathlib import Path

import numpy as np


MAX_SPEED = 2000.0
MIN_DOSERATE = 1.4
MU_EPSILON = 1e-7


def _doserate_file_path() -> Path:
    return Path(__file__).resolve().parent.parent / "LS_doserate.csv"


@lru_cache(maxsize=1)
def load_doserate_table() -> np.ndarray:
    """Load the machine doserate lookup table from the repository CSV."""
    table = np.loadtxt(
        _doserate_file_path(),
        delimiter=",",
        dtype=float,
        encoding="utf-8-sig",
    )
    return np.atleast_2d(table)


def get_doserate_for_energy(energy: float) -> float:
    """Return the configured doserate for an energy bin, or ``0.0`` if missing."""
    table = load_doserate_table()
    if table.size == 0:
        return 0.0
    mask = (energy >= table[:, 0]) & (energy < (table[:, 0] + 0.3))
    matches = table[mask]
    if matches.size == 0:
        return 0.0
    return float(matches[0, 1])


def build_layer_time_trajectory(
    positions_cm: np.ndarray, mu: np.ndarray, energy: float
) -> dict:
    """Build a time trajectory for a planned layer using MU and transit limits."""
    positions_cm = np.asarray(positions_cm, dtype=float)
    mu = np.asarray(mu, dtype=float)

    if positions_cm.ndim != 2 or positions_cm.shape[1] != 2:
        raise ValueError("positions_cm must have shape (n, 2)")
    if mu.ndim != 1 or mu.shape[0] != positions_cm.shape[0]:
        raise ValueError("mu must be a 1D array with same length as positions_cm")

    segment_vectors = positions_cm[1:] - positions_cm[:-1]
    segment_distances = np.linalg.norm(segment_vectors, axis=1)
    segment_distances = np.floor(segment_distances * 10.0) / 10.0  # quantize distance to 1 mm grid
    segment_mu = mu[1:]

    if segment_mu.size > 0:
        mu_per_distance = np.zeros_like(segment_mu)
        distance_mask = segment_distances > 0
        mu_per_distance[distance_mask] = (
            segment_mu[distance_mask] / segment_distances[distance_mask]
        )
        dose_rates = MAX_SPEED * mu_per_distance
        # Exclude transit segments whose geometry-implied doserate falls below
        # MIN_DOSERATE.  These are line-change transits where the beam travels
        # a large distance with near-zero MU — the machine scans them at
        # MAX_SPEED regardless and they should not constrain the layer doserate.
        constraining = dose_rates >= MIN_DOSERATE
        if np.any(constraining):
            min_dose_rate = float(np.min(dose_rates[constraining]))
        else:
            min_dose_rate = MIN_DOSERATE
    else:
        min_dose_rate = MIN_DOSERATE

    doserate_provider = max(get_doserate_for_energy(energy), MIN_DOSERATE)
    if min_dose_rate < MIN_DOSERATE:
        layer_doserate = MIN_DOSERATE
    elif min_dose_rate > doserate_provider:
        layer_doserate = doserate_provider
    else:
        layer_doserate = min_dose_rate

    segment_times = np.zeros_like(segment_distances)
    for i in range(segment_times.shape[0]):
        if segment_mu[i] < MU_EPSILON:
            segment_times[i] = segment_distances[i] / MAX_SPEED
        else:
            dose_time = segment_mu[i] / layer_doserate
            if segment_distances[i] > 0:
                transit_time = segment_distances[i] / MAX_SPEED
                segment_times[i] = max(dose_time, transit_time)
            else:
                segment_times[i] = dose_time

    time_axis = np.zeros(positions_cm.shape[0], dtype=float)
    if segment_times.size > 0:
        time_axis[1:] = np.cumsum(segment_times)

    return {
        "time_axis_s": time_axis,
        "x_cm": positions_cm[:, 0].copy(),
        "y_cm": positions_cm[:, 1].copy(),
        "segment_times_s": np.concatenate(([0.0], segment_times)),
        "layer_doserate_mu_per_s": float(layer_doserate),
        "total_time_s": float(time_axis[-1]),
    }
