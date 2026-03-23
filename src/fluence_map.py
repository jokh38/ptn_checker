import numpy as np


def build_plan_fluence_points(plan_layer, *, exclude_transit_min_dose=True):
    plan_xy = np.asarray(plan_layer.get("positions", []), dtype=float)
    plan_weights = np.asarray(plan_layer.get("mu", []), dtype=float)

    if not exclude_transit_min_dose or plan_xy.size == 0:
        return plan_xy, plan_weights

    keep_mask = ~np.asarray(
        plan_layer.get(
            "spot_is_transit_min_dose",
            np.zeros(len(plan_xy), dtype=bool),
        ),
        dtype=bool,
    )
    return plan_xy[keep_mask], plan_weights[keep_mask]


def assign_log_samples_to_plan_spots(
    plan_xy,
    log_xy,
    sample_weights,
    *,
    spot_tolerance_mm,
):
    plan_xy = np.asarray(plan_xy, dtype=float)
    log_xy = np.asarray(log_xy, dtype=float)
    sample_weights = np.asarray(sample_weights, dtype=float)

    if len(plan_xy) == 0:
        return (
            np.zeros(0, dtype=float),
            float(np.sum(sample_weights)),
            np.zeros(len(log_xy), dtype=bool),
        )
    if len(log_xy) == 0:
        return (
            np.zeros(len(plan_xy), dtype=float),
            0.0,
            np.zeros(0, dtype=bool),
        )

    deltas = log_xy[:, None, :] - plan_xy[None, :, :]
    distances_mm = np.linalg.norm(deltas, axis=2)
    nearest_idx = np.argmin(distances_mm, axis=1)
    nearest_dist = distances_mm[np.arange(len(log_xy)), nearest_idx]
    matched_mask = nearest_dist <= float(spot_tolerance_mm)
    spot_weights = np.bincount(
        nearest_idx[matched_mask],
        weights=sample_weights[matched_mask],
        minlength=len(plan_xy),
    ).astype(float)
    unmatched_weight = float(np.sum(sample_weights[~matched_mask]))
    return spot_weights, unmatched_weight, matched_mask


def rasterize_fluence_points(
    points_xy,
    weights,
    *,
    grid_resolution_mm,
    bounds=None,
    gaussian_sigma_mm=3.0,
    map_margin_mm=0.0,
):
    points_xy = np.asarray(points_xy, dtype=float)
    weights = np.asarray(weights, dtype=float)

    if points_xy.size == 0:
        x_coords = np.array([0.0], dtype=float)
        y_coords = np.array([0.0], dtype=float)
        grid_x, grid_y = np.meshgrid(x_coords, y_coords)
        return grid_x, grid_y, np.zeros_like(grid_x, dtype=float)

    if bounds is None:
        min_xy = np.min(points_xy, axis=0) - float(map_margin_mm)
        max_xy = np.max(points_xy, axis=0) + float(map_margin_mm)
    else:
        min_xy = np.asarray(bounds[0], dtype=float)
        max_xy = np.asarray(bounds[1], dtype=float)

    step = float(grid_resolution_mm)
    x_coords = np.arange(min_xy[0], max_xy[0] + step, step, dtype=float)
    y_coords = np.arange(min_xy[1], max_xy[1] + step, step, dtype=float)
    if x_coords.size == 0:
        x_coords = np.array([min_xy[0]], dtype=float)
    if y_coords.size == 0:
        y_coords = np.array([min_xy[1]], dtype=float)

    grid_x, grid_y = np.meshgrid(x_coords, y_coords)
    grid = np.zeros_like(grid_x, dtype=float)

    sigma = float(gaussian_sigma_mm)
    if sigma <= 0:
        for (x_pos, y_pos), weight in zip(points_xy, weights, strict=False):
            x_idx = int(np.argmin(np.abs(x_coords - x_pos)))
            y_idx = int(np.argmin(np.abs(y_coords - y_pos)))
            grid[y_idx, x_idx] += weight
        return grid_x, grid_y, grid

    for (x_pos, y_pos), weight in zip(points_xy, weights, strict=False):
        dist_sq = (grid_x - x_pos) ** 2 + (grid_y - y_pos) ** 2
        kernel = np.exp(-0.5 * dist_sq / (sigma ** 2))
        kernel_sum = float(np.sum(kernel))
        if kernel_sum > 0:
            grid += weight * (kernel / kernel_sum)

    return grid_x, grid_y, grid
