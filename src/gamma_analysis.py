import numpy as np


def _grid_spacing_mm(grid_x, grid_y):
    x_coords = np.unique(np.asarray(grid_x, dtype=float))
    y_coords = np.unique(np.asarray(grid_y, dtype=float))
    dx = float(np.min(np.diff(x_coords))) if x_coords.size > 1 else np.inf
    dy = float(np.min(np.diff(y_coords))) if y_coords.size > 1 else np.inf
    finite = [value for value in (dx, dy) if np.isfinite(value) and value > 0]
    return min(finite) if finite else 1.0


def perform_fluence_gamma(plan_grid, log_grid, grid_x, grid_y, config):
    plan_grid = np.asarray(plan_grid, dtype=float)
    log_grid = np.asarray(log_grid, dtype=float)
    threshold_percent = float(config["fluence_percent_threshold"])
    distance_threshold_mm = float(config["distance_mm_threshold"])
    lower_cutoff_percent = float(config["lower_percent_fluence_cutoff"])

    plan_max = float(np.max(plan_grid)) if plan_grid.size else 0.0
    cutoff = plan_max * lower_cutoff_percent / 100.0
    evaluated_mask = plan_grid >= cutoff
    evaluated_indices = np.argwhere(evaluated_mask)

    gamma_map = np.full(plan_grid.shape, np.nan, dtype=float)
    if evaluated_indices.size == 0:
        return {
            "pass_rate": 0.0,
            "gamma_mean": np.nan,
            "gamma_max": np.nan,
            "evaluated_point_count": 0,
            "gamma_map": gamma_map,
        }

    spacing_mm = _grid_spacing_mm(grid_x, grid_y)
    radius_cells = max(int(np.ceil(distance_threshold_mm / spacing_mm)), 0)
    dose_threshold = plan_max * threshold_percent / 100.0
    if dose_threshold <= 0:
        dose_threshold = 1e-12

    gamma_values = []
    for row_idx, col_idx in evaluated_indices:
        row_start = max(0, row_idx - radius_cells)
        row_end = min(plan_grid.shape[0], row_idx + radius_cells + 1)
        col_start = max(0, col_idx - radius_cells)
        col_end = min(plan_grid.shape[1], col_idx + radius_cells + 1)

        local_log = log_grid[row_start:row_end, col_start:col_end]
        local_rows, local_cols = np.indices(local_log.shape)
        eval_rows = local_rows + row_start
        eval_cols = local_cols + col_start
        distance_mm = np.sqrt(
            ((eval_rows - row_idx) * spacing_mm) ** 2
            + ((eval_cols - col_idx) * spacing_mm) ** 2
        )
        gamma_local = np.sqrt(
            (distance_mm / distance_threshold_mm) ** 2
            + ((local_log - plan_grid[row_idx, col_idx]) / dose_threshold) ** 2
        )
        gamma_value = float(np.min(gamma_local))
        gamma_map[row_idx, col_idx] = gamma_value
        gamma_values.append(gamma_value)

    gamma_values = np.asarray(gamma_values, dtype=float)
    return {
        "pass_rate": float(np.mean(gamma_values <= 1.0)),
        "gamma_mean": float(np.mean(gamma_values)),
        "gamma_max": float(np.max(gamma_values)),
        "evaluated_point_count": int(gamma_values.size),
        "gamma_map": gamma_map,
    }
