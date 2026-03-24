import numpy as np

from src.calculator import (
    _assign_samples_to_spots,
    _boundary_carryover_mask,
    _detect_settling,
    _normalized_spot_series,
)


FIXED_SAMPLE_INTERVAL_S = 60e-6
DIRECT_GAMMA_MAP_RESOLUTION_MM = 0.5


def _normalize_log_counts(log_data, config):
    counts = np.asarray(log_data.get("dose1_au", []), dtype=float)
    normalization_factor = config.get("GAMMA_NORMALIZATION_FACTOR")
    if normalization_factor is not None:
        return counts * float(normalization_factor)
    return counts


def _build_fixed_time_axis(plan_layer, log_data, dt_s=FIXED_SAMPLE_INTERVAL_S):
    plan_time_s = np.asarray(plan_layer.get("time_axis_s", []), dtype=float)
    log_time_ms = np.asarray(log_data.get("time_ms", []), dtype=float)

    if plan_time_s.size == 0 and log_time_ms.size == 0:
        return np.zeros(0, dtype=float)

    log_time_s = np.zeros_like(log_time_ms, dtype=float)
    if log_time_ms.size > 0:
        log_time_s = (log_time_ms - float(log_time_ms[0])) / 1000.0

    t_end = 0.0
    if plan_time_s.size > 0:
        t_end = max(t_end, float(plan_time_s[-1]))
    if log_time_s.size > 0:
        t_end = max(t_end, float(log_time_s[-1]))

    return np.arange(0.0, t_end + dt_s * 0.5, dt_s, dtype=float)


def _per_sample_counts_from_cumulative(cumulative_values):
    cumulative = np.asarray(cumulative_values, dtype=float)
    if cumulative.size == 0:
        return np.zeros(0, dtype=float)

    per_sample = np.diff(cumulative, prepend=cumulative[0])
    per_sample[0] = max(float(cumulative[0]), 0.0)
    return per_sample


def _build_time_aligned_series(plan_layer, log_data, config, *, dt_s=FIXED_SAMPLE_INTERVAL_S):
    time_s = _build_fixed_time_axis(plan_layer, log_data, dt_s=dt_s)
    if time_s.size == 0:
        return {
            "time_s": time_s,
            "plan_x": np.zeros(0, dtype=float),
            "plan_y": np.zeros(0, dtype=float),
            "plan_cumulative_mu": np.zeros(0, dtype=float),
            "plan_count": np.zeros(0, dtype=float),
            "log_x": np.zeros(0, dtype=float),
            "log_y": np.zeros(0, dtype=float),
            "log_count": np.zeros(0, dtype=float),
        }

    plan_time_s = np.asarray(plan_layer.get("time_axis_s", []), dtype=float)
    plan_x = np.asarray(plan_layer.get("trajectory_x_mm", []), dtype=float)
    plan_y = np.asarray(plan_layer.get("trajectory_y_mm", []), dtype=float)
    plan_cumulative_mu = np.asarray(plan_layer.get("cumulative_mu", []), dtype=float)
    if (
        plan_time_s.size == 0
        or plan_time_s.size != plan_x.size
        or plan_time_s.size != plan_y.size
        or plan_time_s.size != plan_cumulative_mu.size
    ):
        raise ValueError("plan_layer must provide matching time_axis_s, trajectory_x_mm, trajectory_y_mm, and cumulative_mu arrays")

    interp_plan_x = np.interp(time_s, plan_time_s, plan_x)
    interp_plan_y = np.interp(time_s, plan_time_s, plan_y)
    interp_plan_cumulative_mu = np.interp(time_s, plan_time_s, plan_cumulative_mu)
    plan_count = _per_sample_counts_from_cumulative(interp_plan_cumulative_mu)

    log_time_ms = np.asarray(log_data.get("time_ms", []), dtype=float)
    log_x = np.asarray(log_data.get("x_mm", log_data.get("x", [])), dtype=float)
    log_y = np.asarray(log_data.get("y_mm", log_data.get("y", [])), dtype=float)
    log_count = _normalize_log_counts(log_data, config)
    if (
        log_time_ms.size == 0
        or log_time_ms.size != log_x.size
        or log_time_ms.size != log_y.size
        or log_time_ms.size != log_count.size
    ):
        raise ValueError("log_data must provide matching time_ms, x/y, and dose1_au arrays")

    log_time_s = (log_time_ms - float(log_time_ms[0])) / 1000.0
    interp_log_x = np.interp(time_s, log_time_s, log_x)
    interp_log_y = np.interp(time_s, log_time_s, log_y)
    interp_log_count = np.interp(time_s, log_time_s, log_count)

    return {
        "time_s": time_s,
        "plan_x": interp_plan_x,
        "plan_y": interp_plan_y,
        "plan_cumulative_mu": interp_plan_cumulative_mu,
        "plan_count": plan_count,
        "log_x": interp_log_x,
        "log_y": interp_log_y,
        "log_count": interp_log_count,
    }


def _build_direct_gamma_map(x_mm, y_mm, gamma_values, *, resolution_mm=DIRECT_GAMMA_MAP_RESOLUTION_MM):
    x_mm = np.asarray(x_mm, dtype=float)
    y_mm = np.asarray(y_mm, dtype=float)
    gamma_values = np.asarray(gamma_values, dtype=float)
    if x_mm.size == 0 or y_mm.size == 0 or gamma_values.size == 0:
        return np.full((1, 1), np.nan, dtype=float)

    min_x, max_x = float(np.min(x_mm)), float(np.max(x_mm))
    min_y, max_y = float(np.min(y_mm)), float(np.max(y_mm))
    x_coords = np.arange(min_x, max_x + resolution_mm, resolution_mm, dtype=float)
    y_coords = np.arange(min_y, max_y + resolution_mm, resolution_mm, dtype=float)
    if x_coords.size < 2:
        x_coords = np.array([min_x, min_x + resolution_mm], dtype=float)
    if y_coords.size < 2:
        y_coords = np.array([min_y, min_y + resolution_mm], dtype=float)

    accum = np.zeros((y_coords.size, x_coords.size), dtype=float)
    counts = np.zeros_like(accum)
    x_idx = np.clip(np.round((x_mm - x_coords[0]) / resolution_mm).astype(int), 0, x_coords.size - 1)
    y_idx = np.clip(np.round((y_mm - y_coords[0]) / resolution_mm).astype(int), 0, y_coords.size - 1)
    valid = np.isfinite(gamma_values)
    for xi, yi, gamma in zip(x_idx[valid], y_idx[valid], gamma_values[valid], strict=False):
        accum[yi, xi] += gamma
        counts[yi, xi] += 1.0

    gamma_map = np.full_like(accum, np.nan)
    nonzero = counts > 0
    gamma_map[nonzero] = accum[nonzero] / counts[nonzero]
    return gamma_map


def _build_analysis_sample_masks(plan_layer, aligned, config):
    time_s = np.asarray(aligned["time_s"], dtype=float)
    plan_x = np.asarray(aligned["plan_x"], dtype=float)
    plan_y = np.asarray(aligned["plan_y"], dtype=float)
    log_x = np.asarray(aligned["log_x"], dtype=float)
    log_y = np.asarray(aligned["log_y"], dtype=float)
    plan_time_s = np.asarray(plan_layer.get("time_axis_s", []), dtype=float)

    if time_s.size == 0 or plan_x.size == 0 or plan_y.size == 0:
        empty_bool = np.zeros(0, dtype=bool)
        empty_int = np.zeros(0, dtype=int)
        empty_float = np.zeros(0, dtype=float)
        return {
            "settling_index": 0,
            "settling_status": "insufficient_data",
            "is_settling": empty_bool,
            "settled_mask": empty_bool,
            "assigned_spot_index": empty_int,
            "assigned_spot_mu": empty_float,
            "assigned_spot_scan_speed_mm_s": empty_float,
            "sample_is_transit_min_dose": empty_bool,
            "sample_is_boundary_carryover": empty_bool,
            "analysis_mask": empty_bool,
            "num_filtered_samples": 0,
        }

    config = config or {}
    settling_index, settling_status = _detect_settling(
        log_x,
        log_y,
        time_s,
        target_x=plan_x[0],
        target_y=plan_y[0],
        threshold=config.get("SETTLING_THRESHOLD_MM", 0.5),
        consecutive=config.get("SETTLING_CONSECUTIVE_SAMPLES", 10),
    )
    is_settling = np.arange(time_s.size) < settling_index
    settled_mask = ~is_settling

    assigned_spot_index = _assign_samples_to_spots(time_s, plan_time_s)
    spot_mu, spot_is_transit_min_dose, spot_scan_speed_mm_s = _normalized_spot_series(
        plan_layer,
        plan_time_s,
    )
    sample_is_transit_min_dose = spot_is_transit_min_dose[assigned_spot_index]
    sample_is_boundary_carryover = _boundary_carryover_mask(
        config,
        plan_time_s,
        time_s,
        assigned_spot_index,
        spot_is_transit_min_dose,
    )
    zero_dose_filter_enabled = bool(config.get("ZERO_DOSE_FILTER_ENABLED", False))
    filtered_mask = (
        settled_mask
        & (~sample_is_transit_min_dose)
        & (~sample_is_boundary_carryover)
    )
    analysis_mask = filtered_mask if zero_dose_filter_enabled else settled_mask.copy()

    return {
        "settling_index": int(settling_index),
        "settling_status": settling_status,
        "is_settling": is_settling,
        "settled_mask": settled_mask,
        "assigned_spot_index": assigned_spot_index,
        "assigned_spot_mu": spot_mu[assigned_spot_index],
        "assigned_spot_scan_speed_mm_s": spot_scan_speed_mm_s[assigned_spot_index],
        "sample_is_transit_min_dose": sample_is_transit_min_dose,
        "sample_is_boundary_carryover": sample_is_boundary_carryover,
        "analysis_mask": analysis_mask,
        "num_filtered_samples": int(np.sum(settled_mask & (~filtered_mask))),
    }


def _calculate_direct_gamma_results(aligned, config, analysis_mask=None):
    plan_count = np.asarray(aligned["plan_count"], dtype=float)
    log_count = np.asarray(aligned["log_count"], dtype=float)
    plan_x = np.asarray(aligned["plan_x"], dtype=float)
    plan_y = np.asarray(aligned["plan_y"], dtype=float)
    log_x = np.asarray(aligned["log_x"], dtype=float)
    log_y = np.asarray(aligned["log_y"], dtype=float)

    if plan_count.size == 0:
        return {
            "pass_rate": 0.0,
            "gamma_mean": np.nan,
            "gamma_max": np.nan,
            "evaluated_point_count": 0,
            "gamma_values": np.zeros(0, dtype=float),
            "gamma_map": np.full((1, 1), np.nan, dtype=float),
            "position_error_mean_mm": np.nan,
            "count_error_mean": np.nan,
        }

    position_error_mm = np.sqrt((log_x - plan_x) ** 2 + (log_y - plan_y) ** 2)
    count_error = log_count - plan_count
    peak_plan_count = float(np.max(plan_count)) if plan_count.size else 0.0
    cutoff = peak_plan_count * float(config["GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF"]) / 100.0
    if analysis_mask is None:
        analysis_mask = np.ones_like(plan_count, dtype=bool)
    else:
        analysis_mask = np.asarray(analysis_mask, dtype=bool)
    evaluated = analysis_mask & (plan_count >= cutoff)

    if not np.any(evaluated):
        return {
            "pass_rate": 0.0,
            "gamma_mean": np.nan,
            "gamma_max": np.nan,
            "evaluated_point_count": 0,
            "gamma_values": np.zeros(0, dtype=float),
            "gamma_map": np.full((1, 1), np.nan, dtype=float),
            "position_error_mean_mm": np.nan,
            "count_error_mean": np.nan,
        }

    dose_threshold = peak_plan_count * float(config["GAMMA_FLUENCE_PERCENT_THRESHOLD"]) / 100.0
    if dose_threshold <= 0:
        dose_threshold = 1e-12
    distance_threshold = float(config["GAMMA_DISTANCE_MM_THRESHOLD"])
    gamma_values = np.sqrt(
        (position_error_mm[evaluated] / distance_threshold) ** 2
        + (count_error[evaluated] / dose_threshold) ** 2
    )

    gamma_map = _build_direct_gamma_map(
        log_x[evaluated],
        log_y[evaluated],
        gamma_values,
    )
    return {
        "pass_rate": float(np.mean(gamma_values <= 1.0)),
        "gamma_mean": float(np.mean(gamma_values)),
        "gamma_max": float(np.max(gamma_values)),
        "evaluated_point_count": int(gamma_values.size),
        "gamma_values": gamma_values,
        "gamma_map": gamma_map,
        "position_error_mean_mm": float(np.mean(position_error_mm[evaluated])),
        "count_error_mean": float(np.mean(np.abs(count_error[evaluated]))),
    }


def calculate_point_gamma_for_layer(plan_layer, log_data, config):
    if "time_axis_s" not in plan_layer or "trajectory_x_mm" not in plan_layer:
        return {"error": "No planned treatment trajectory available for point gamma analysis"}
    if "time_ms" not in log_data:
        return {"error": "Point gamma analysis requires time-aligned log samples"}

    aligned = _build_time_aligned_series(plan_layer, log_data, config)
    analysis_masks = _build_analysis_sample_masks(plan_layer, aligned, config)
    results = _calculate_direct_gamma_results(
        aligned,
        config,
        analysis_mask=analysis_masks["analysis_mask"],
    )
    diff_x = np.asarray(aligned["log_x"], dtype=float) - np.asarray(aligned["plan_x"], dtype=float)
    diff_y = np.asarray(aligned["log_y"], dtype=float) - np.asarray(aligned["plan_y"], dtype=float)
    mask = analysis_masks["analysis_mask"]
    stats_diff_x = diff_x[mask] if np.any(mask) else diff_x
    stats_diff_y = diff_y[mask] if np.any(mask) else diff_y
    abs_stats_diff_x = np.abs(stats_diff_x)
    abs_stats_diff_y = np.abs(stats_diff_y)
    results.update(
        {
            "diff_x": diff_x,
            "diff_y": diff_y,
            "mean_diff_x": float(np.mean(stats_diff_x)) if stats_diff_x.size else 0.0,
            "mean_diff_y": float(np.mean(stats_diff_y)) if stats_diff_y.size else 0.0,
            "std_diff_x": float(np.std(stats_diff_x)) if stats_diff_x.size else 0.0,
            "std_diff_y": float(np.std(stats_diff_y)) if stats_diff_y.size else 0.0,
            "rmse_x": float(np.sqrt(np.mean(stats_diff_x**2))) if stats_diff_x.size else 0.0,
            "rmse_y": float(np.sqrt(np.mean(stats_diff_y**2))) if stats_diff_y.size else 0.0,
            "max_abs_diff_x": float(np.max(abs_stats_diff_x)) if abs_stats_diff_x.size else 0.0,
            "max_abs_diff_y": float(np.max(abs_stats_diff_y)) if abs_stats_diff_y.size else 0.0,
            "p95_abs_diff_x": float(np.percentile(abs_stats_diff_x, 95)) if abs_stats_diff_x.size else 0.0,
            "p95_abs_diff_y": float(np.percentile(abs_stats_diff_y, 95)) if abs_stats_diff_y.size else 0.0,
            "is_settling": analysis_masks["is_settling"],
            "settling_index": analysis_masks["settling_index"],
            "settling_samples_count": int(np.sum(analysis_masks["is_settling"])),
            "settling_status": analysis_masks["settling_status"],
            "assigned_spot_index": analysis_masks["assigned_spot_index"],
            "assigned_spot_mu": analysis_masks["assigned_spot_mu"],
            "assigned_spot_scan_speed_mm_s": analysis_masks["assigned_spot_scan_speed_mm_s"],
            "sample_is_transit_min_dose": analysis_masks["sample_is_transit_min_dose"],
            "sample_is_boundary_carryover": analysis_masks["sample_is_boundary_carryover"],
            "sample_is_included_filtered_stats": analysis_masks["analysis_mask"],
            "num_filtered_samples": analysis_masks["num_filtered_samples"],
            "num_included_samples": int(np.sum(analysis_masks["analysis_mask"])),
            "plan_positions": np.column_stack((aligned["plan_x"], aligned["plan_y"])),
            "log_positions": np.column_stack((aligned["log_x"], aligned["log_y"])),
            "plan_grid": np.vstack((aligned["plan_x"], aligned["plan_y"], aligned["plan_count"])),
            "log_grid": np.vstack((aligned["log_x"], aligned["log_y"], aligned["log_count"])),
            "plan_fluence_max": float(np.max(aligned["plan_count"])) if aligned["plan_count"].size else 0.0,
            "log_fluence_max": float(np.max(aligned["log_count"])) if aligned["log_count"].size else 0.0,
            "gamma_pass_rate_percent": float(results.get("pass_rate", 0.0)) * 100.0,
            "normalization_mode": "point_gamma",
            "used_planrange_mu_correction": False,
            "unmatched_delivered_weight": 0.0,
        }
    )
    return results
