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
    values = []
    with _doserate_file_path().open("r", encoding="utf-8") as file_obj:
        for line_number, raw_line in enumerate(file_obj):
            if line_number == 0:
                continue
            cleaned = (
                raw_line.replace("[", " ").replace("]", " ").replace(";", " ").strip()
            )
            if not cleaned:
                continue
            parts = cleaned.split()
            if len(parts) != 2:
                continue
            values.append((float(parts[0]), float(parts[1])))
    return np.asarray(values, dtype=float)


def get_doserate_for_energy(energy: float) -> float:
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
    positions_cm = np.asarray(positions_cm, dtype=float)
    mu = np.asarray(mu, dtype=float)

    if positions_cm.ndim != 2 or positions_cm.shape[1] != 2:
        raise ValueError("positions_cm must have shape (n, 2)")
    if mu.ndim != 1 or mu.shape[0] != positions_cm.shape[0]:
        raise ValueError("mu must be a 1D array with same length as positions_cm")

    segment_vectors = positions_cm[1:] - positions_cm[:-1]
    segment_distances = np.linalg.norm(segment_vectors, axis=1)
    segment_mu = mu[1:]

    if segment_mu.size > 0:
        mu_per_distance = np.zeros_like(segment_mu)
        distance_mask = segment_distances > 0
        mu_per_distance[distance_mask] = (
            segment_mu[distance_mask] / segment_distances[distance_mask]
        )
        dose_rates = MAX_SPEED * mu_per_distance
        min_dose_rate = float(np.min(dose_rates))
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
            segment_times[i] = segment_mu[i] / layer_doserate

    time_axis = np.zeros(positions_cm.shape[0], dtype=float)
    if segment_times.size > 0:
        time_axis[1:] = np.cumsum(segment_times)

    return {
        "time_axis_s": time_axis,
        "x_cm": positions_cm[:, 0].copy(),
        "y_cm": positions_cm[:, 1].copy(),
        "layer_doserate_mu_per_s": float(layer_doserate),
        "total_time_s": float(time_axis[-1]),
    }
