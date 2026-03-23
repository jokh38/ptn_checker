import numpy as np

from src.fluence_map import (
    assign_log_samples_to_plan_spots,
    build_plan_fluence_points,
    rasterize_fluence_points,
)
from src.gamma_analysis import perform_fluence_gamma


def _select_log_weights(log_data, config):
    planrange_metadata = log_data.get("planrange_metadata", {})
    require_correction = bool(config.get("GAMMA_REQUIRE_PLANRANGE_MU_CORRECTION", True))
    allow_fallback = bool(config.get("GAMMA_ALLOW_RELATIVE_FLUENCE_FALLBACK", True))

    if planrange_metadata.get("applied"):
        return (
            np.asarray(log_data.get("mu_per_sample_corrected", []), dtype=float),
            "planrange_corrected",
            True,
        )

    if require_correction and not allow_fallback:
        raise ValueError("PlanRange MU correction is required for gamma analysis")

    return (
        np.asarray(log_data.get("dose1_au", []), dtype=float),
        "relative_fluence",
        False,
    )


def _normalize_pair(plan_grid, log_grid, normalization_mode):
    if normalization_mode != "relative_fluence":
        return plan_grid, log_grid

    plan_sum = float(np.sum(plan_grid))
    log_sum = float(np.sum(log_grid))
    if plan_sum > 0:
        plan_grid = plan_grid / plan_sum
    if log_sum > 0:
        log_grid = log_grid / log_sum
    return plan_grid, log_grid


def _apply_primary_normalization(log_grid, config, normalization_mode):
    if normalization_mode != "planrange_corrected":
        return log_grid

    normalization_factor = config.get("GAMMA_NORMALIZATION_FACTOR")
    if normalization_factor is None:
        return log_grid

    return log_grid * float(normalization_factor)


def calculate_gamma_for_layer(plan_layer, log_data, config):
    plan_xy, plan_weights = build_plan_fluence_points(plan_layer)
    if len(plan_xy) == 0:
        return {"error": "No planned treatment spots available for gamma analysis"}

    log_xy = np.column_stack(
        (
            np.asarray(log_data.get("x_mm", log_data.get("x", [])), dtype=float),
            np.asarray(log_data.get("y_mm", log_data.get("y", [])), dtype=float),
        )
    )
    sample_weights, normalization_mode, used_correction = _select_log_weights(
        log_data,
        config,
    )
    if len(log_xy) != len(sample_weights):
        return {"error": "Gamma analysis requires one delivered weight per log sample"}

    delivered_spot_weights, unmatched_weight, _ = assign_log_samples_to_plan_spots(
        plan_xy,
        log_xy,
        sample_weights,
        spot_tolerance_mm=float(config["GAMMA_SPOT_TOLERANCE_MM"]),
    )

    all_points = plan_xy if len(log_xy) == 0 else np.vstack((plan_xy, log_xy))
    margin = float(config.get("GAMMA_MAP_MARGIN_MM", 0.0))
    bounds = (
        np.min(all_points, axis=0) - margin,
        np.max(all_points, axis=0) + margin,
    )

    gaussian_sigma_mm = (
        float(config["GAMMA_GAUSSIAN_SIGMA_MM"])
        if bool(config.get("GAMMA_USE_GAUSSIAN_SPOT_MODEL", True))
        else 0.0
    )

    grid_x, grid_y, plan_grid = rasterize_fluence_points(
        plan_xy,
        plan_weights,
        grid_resolution_mm=float(config["GAMMA_GRID_RESOLUTION_MM"]),
        bounds=bounds,
        gaussian_sigma_mm=gaussian_sigma_mm,
    )
    _, _, log_grid = rasterize_fluence_points(
        plan_xy,
        delivered_spot_weights,
        grid_resolution_mm=float(config["GAMMA_GRID_RESOLUTION_MM"]),
        bounds=bounds,
        gaussian_sigma_mm=gaussian_sigma_mm,
    )

    plan_grid, log_grid = _normalize_pair(plan_grid, log_grid, normalization_mode)
    log_grid = _apply_primary_normalization(log_grid, config, normalization_mode)
    gamma_results = perform_fluence_gamma(
        plan_grid,
        log_grid,
        grid_x,
        grid_y,
        {
            "fluence_percent_threshold": config["GAMMA_FLUENCE_PERCENT_THRESHOLD"],
            "distance_mm_threshold": config["GAMMA_DISTANCE_MM_THRESHOLD"],
            "lower_percent_fluence_cutoff": config["GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF"],
        },
    )
    gamma_results.update(
        {
            "plan_fluence_max": float(np.max(plan_grid)) if plan_grid.size else 0.0,
            "log_fluence_max": float(np.max(log_grid)) if log_grid.size else 0.0,
            "normalization_mode": normalization_mode,
            "used_planrange_mu_correction": used_correction,
            "unmatched_delivered_weight": float(unmatched_weight),
            "plan_positions": plan_xy,
            "log_positions": log_xy,
            "plan_grid": plan_grid,
            "log_grid": log_grid,
        }
    )
    return gamma_results
