import logging

import numpy as np
from scipy.optimize import curve_fit

logger = logging.getLogger(__name__)

# Histogram parameters for position difference analysis
HISTOGRAM_RANGE_MM = (-5, 5)  # histogram range in mm
HISTOGRAM_BIN_STEP = 0.01  # histogram bin width in mm
DEFAULT_SETTLING_THRESHOLD_MM = 0.5
DEFAULT_SETTLING_CONSECUTIVE_SAMPLES = 10
DEFAULT_SETTLING_SEARCH_WINDOW_S = 0.001
DEFAULT_ZERO_DOSE_BOUNDARY_HOLDOFF_S = 0.0006
DEFAULT_ZERO_DOSE_POST_MINIMAL_DOSE_BOUNDARY_S = 0.001


def gaussian(x, amplitude, mean, stddev):
    """Gaussian function for curve fitting."""
    return amplitude * np.exp(-((x - mean) / stddev)**2 / 2)


def _detect_settling(
    log_x,
    log_y,
    log_time_s,
    target_x,
    target_y,
    threshold,
    consecutive,
    window_s=None,
):
    """Find the first stable arrival near the layer's starting plan position."""
    log_x = np.asarray(log_x, dtype=float)
    log_y = np.asarray(log_y, dtype=float)
    log_time_s = np.asarray(log_time_s, dtype=float)

    if log_x.size == 0 or log_y.size == 0 or log_time_s.size == 0:
        return 0, "insufficient_data"

    if window_s is None:
        window_s = DEFAULT_SETTLING_SEARCH_WINDOW_S
    search_mask = log_time_s <= float(window_s)
    search_length = int(np.sum(search_mask))
    search_length = min(search_length, log_x.size, log_y.size)
    if search_length < int(consecutive):
        return 0, "insufficient_data"

    within_threshold = (
        np.abs(log_x[:search_length] - float(target_x)) < float(threshold)
    ) & (
        np.abs(log_y[:search_length] - float(target_y)) < float(threshold)
    )
    run_length = int(consecutive)
    for start in range(0, search_length - run_length + 1):
        if np.all(within_threshold[start:start + run_length]):
            return start, "settled"
    return search_length, "never_settled"


def _calculate_axis_stats(diff):
    return {
        "mean": np.mean(diff),
        "std": np.std(diff),
        "rmse": np.sqrt(np.mean(diff ** 2)),
        "max_abs": np.max(np.abs(diff)),
        "p95_abs": np.percentile(np.abs(diff), 95),
    }


def _get_optional_series(data, key, length, warning_context):
    if key not in data:
        logger.warning(
            "Missing optional %s key '%s'; filling debug CSV values with zeros",
            warning_context,
            key,
        )
        return np.zeros(length, dtype=float)

    values = np.asarray(data[key], dtype=float)
    if len(values) != length:
        logger.warning(
            "Unexpected %s key '%s' length %s (expected %s); filling debug CSV values with zeros",
            warning_context,
            key,
            len(values),
            length,
        )
        return np.zeros(length, dtype=float)

    return values


def _assign_samples_to_spots(log_time_s, spot_time_axis_s):
    spot_time_axis_s = np.asarray(spot_time_axis_s, dtype=float)
    if spot_time_axis_s.size == 0:
        return np.zeros(0, dtype=int)
    assigned = np.searchsorted(spot_time_axis_s, log_time_s, side="left")
    return np.clip(assigned, 0, len(spot_time_axis_s) - 1)


def _calculate_stats_with_fallback(primary_x, primary_y, fallback_x, fallback_y):
    if primary_x.size > 0 and primary_y.size > 0:
        return (
            _calculate_axis_stats(primary_x),
            _calculate_axis_stats(primary_y),
            False,
            primary_x,
            primary_y,
        )
    return (
        _calculate_axis_stats(fallback_x),
        _calculate_axis_stats(fallback_y),
        True,
        fallback_x,
        fallback_y,
    )


def calculate_differences_for_layer(
    plan_layer,
    log_data,
    save_to_csv=False,
    csv_filename="debug_layer_data.csv",
    config=None,
):
    """
    Calculates the differences between planned and actual data for a single layer.

    Args:
        plan_layer: A dictionary containing the plan data for a single layer.
        log_data: Parsed data from a PTN log file for the corresponding layer.
        save_to_csv (bool): If True, saves the interpolated plan and log data to a CSV file.
        csv_filename (str): The name of the CSV file to save.
        config (dict | None): Parsed analysis configuration.

    Returns:
        A dictionary containing the analysis results for the layer.
    """
    results = {}

    for key in ('time_axis_s', 'trajectory_x_mm', 'trajectory_y_mm'):
        if key not in plan_layer:
            return {'error': f"Missing required plan_layer key: '{key}'"}

    for key in ('time_ms', 'x', 'y'):
        if key not in log_data:
            return {'error': f"Missing required log_data key: '{key}'"}

    plan_time_s = np.asarray(plan_layer['time_axis_s'], dtype=float)
    plan_x = np.asarray(plan_layer['trajectory_x_mm'], dtype=float)
    plan_y = np.asarray(plan_layer['trajectory_y_mm'], dtype=float)

    log_time_s = (np.asarray(log_data['time_ms'], dtype=float) -
                  float(log_data['time_ms'][0])) / 1000.0
    log_x = np.asarray(log_data['x'], dtype=float)
    log_y = np.asarray(log_data['y'], dtype=float)

    if len(plan_time_s) == 0 or len(log_time_s) == 0:
        return {'error': 'Empty data arrays'}

    interp_plan_x = np.interp(log_time_s, plan_time_s, plan_x)
    interp_plan_y = np.interp(log_time_s, plan_time_s, plan_y)
    plan_cumulative_mu = _get_optional_series(
        plan_layer,
        "cumulative_mu",
        len(plan_time_s),
        "plan_layer",
    )
    interp_plan_mu = np.interp(log_time_s, plan_time_s, plan_cumulative_mu)
    log_mu = _get_optional_series(log_data, "mu", len(log_time_s), "log_data")

    dx = np.diff(log_x, prepend=log_x[0])
    dy = np.diff(log_y, prepend=log_y[0])
    dt = np.diff(log_time_s, prepend=log_time_s[0])
    log_velocity_mm_s = np.zeros_like(dt)
    nonzero_dt = dt > 0
    log_velocity_mm_s[nonzero_dt] = (
        np.sqrt(dx[nonzero_dt] ** 2 + dy[nonzero_dt] ** 2) / dt[nonzero_dt]
    )

    diff_x = interp_plan_x - log_x
    diff_y = interp_plan_y - log_y

    config = config or {}
    settling_index, settling_status = _detect_settling(
        log_x,
        log_y,
        log_time_s,
        target_x=plan_x[0],
        target_y=plan_y[0],
        threshold=config.get("SETTLING_THRESHOLD_MM", DEFAULT_SETTLING_THRESHOLD_MM),
        consecutive=config.get(
            "SETTLING_CONSECUTIVE_SAMPLES",
            DEFAULT_SETTLING_CONSECUTIVE_SAMPLES,
        ),
    )
    is_settling = np.arange(len(diff_x)) < settling_index
    settled_mask = ~is_settling
    stats_diff_x = diff_x[settled_mask] if np.any(settled_mask) else diff_x
    stats_diff_y = diff_y[settled_mask] if np.any(settled_mask) else diff_y

    assigned_spot_index = _assign_samples_to_spots(log_time_s, plan_time_s)
    spot_mu = np.asarray(
        plan_layer.get("mu", np.zeros(len(plan_time_s), dtype=float)),
        dtype=float,
    )
    if spot_mu.shape[0] != len(plan_time_s):
        spot_mu = np.zeros(len(plan_time_s), dtype=float)
    spot_is_transit_min_dose = np.asarray(
        plan_layer.get(
            "spot_is_transit_min_dose",
            np.zeros(len(plan_time_s), dtype=bool),
        ),
        dtype=bool,
    )
    if spot_is_transit_min_dose.shape[0] != len(plan_time_s):
        spot_is_transit_min_dose = np.zeros(len(plan_time_s), dtype=bool)
    spot_scan_speed_mm_s = np.asarray(
        plan_layer.get(
            "spot_scan_speed_mm_s",
            np.zeros(len(plan_time_s), dtype=float),
        ),
        dtype=float,
    )
    if spot_scan_speed_mm_s.shape[0] != len(plan_time_s):
        spot_scan_speed_mm_s = np.zeros(len(plan_time_s), dtype=float)

    sample_is_transit_min_dose = spot_is_transit_min_dose[assigned_spot_index]
    sample_is_boundary_carryover = np.zeros(len(diff_x), dtype=bool)
    boundary_holdoff_s = float(
        config.get(
            "ZERO_DOSE_BOUNDARY_HOLDOFF_S",
            DEFAULT_ZERO_DOSE_BOUNDARY_HOLDOFF_S,
        )
    )
    post_minimal_dose_boundary_s = float(
        config.get(
            "ZERO_DOSE_POST_MINIMAL_DOSE_BOUNDARY_S",
            DEFAULT_ZERO_DOSE_POST_MINIMAL_DOSE_BOUNDARY_S,
        )
    )
    treatment_after_transit = np.flatnonzero(
        (~spot_is_transit_min_dose[1:]) & spot_is_transit_min_dose[:-1]
    ) + 1
    if boundary_holdoff_s > 0:
        for spot_idx in treatment_after_transit:
            spot_start_s = plan_time_s[spot_idx - 1]
            spot_samples = assigned_spot_index == spot_idx
            sample_is_boundary_carryover |= (
                spot_samples
                & ((log_time_s - spot_start_s) < boundary_holdoff_s)
            )
    if post_minimal_dose_boundary_s > 0:
        for spot_idx in treatment_after_transit:
            spot_start_s = plan_time_s[spot_idx - 1]
            spot_samples = assigned_spot_index == spot_idx
            elapsed_s = log_time_s - spot_start_s
            sample_is_boundary_carryover |= (
                spot_samples
                & (elapsed_s >= 0)
                & (elapsed_s < post_minimal_dose_boundary_s)
            )

    zero_dose_filter_enabled = bool(config.get("ZERO_DOSE_FILTER_ENABLED", False))
    filtered_mask = (
        settled_mask
        & (~sample_is_transit_min_dose)
        & (~sample_is_boundary_carryover)
    )
    sample_is_included_filtered_stats = (
        filtered_mask if zero_dose_filter_enabled else settled_mask.copy()
    )

    filtered_stats_x = filtered_stats_y = None
    filtered_stats_fallback_to_raw = False
    filtered_diff_x = filtered_diff_y = None
    if zero_dose_filter_enabled:
        (
            filtered_stats_x,
            filtered_stats_y,
            filtered_stats_fallback_to_raw,
            filtered_diff_x,
            filtered_diff_y,
        ) = _calculate_stats_with_fallback(
            diff_x[filtered_mask],
            diff_y[filtered_mask],
            stats_diff_x,
            stats_diff_y,
        )

    plan_end = float(plan_time_s[-1]) if len(plan_time_s) else 0.0
    log_end = float(log_time_s[-1]) if len(log_time_s) else 0.0
    max_end = max(plan_end, log_end)
    overlap = min(plan_end, log_end) / max_end if max_end > 0 else 1.0
    if overlap < 0.95:
        logger.warning(f"Plan/log time overlap: {overlap:.1%}")

    # Save to CSV if requested
    if save_to_csv:
        logger.info(f"Saving data to {csv_filename}")
        data_to_save = np.column_stack((
            log_time_s,
            interp_plan_x,
            interp_plan_y,
            log_x,
            log_y,
            log_data['x_raw'],
            log_data['y_raw'],
            log_data['layer_num'],
            log_data['beam_on_off'],
            is_settling.astype(int),
            log_velocity_mm_s,
            interp_plan_mu,
            log_mu,
            assigned_spot_index,
            spot_mu[assigned_spot_index],
            spot_scan_speed_mm_s[assigned_spot_index],
            sample_is_transit_min_dose.astype(int),
            sample_is_boundary_carryover.astype(int),
            sample_is_included_filtered_stats.astype(int),
        ))
        header = (
            "log_time_s,interp_plan_x,interp_plan_y,log_x,log_y,x_raw,y_raw,"
            "layer_num,beam_on_off,is_settling,log_velocity_mm_s,interp_plan_mu,log_mu,"
            "assigned_spot_index,assigned_spot_mu,assigned_spot_scan_speed_mm_s,"
            "sample_is_transit_min_dose,sample_is_boundary_carryover,"
            "sample_is_included_filtered_stats"
        )
        np.savetxt(csv_filename, data_to_save, delimiter=",", header=header, comments="")

    results['diff_x'] = diff_x
    results['diff_y'] = diff_y
    results['is_settling'] = is_settling
    results['settling_index'] = int(settling_index)
    results['settling_samples_count'] = int(np.sum(is_settling))
    results['settling_status'] = settling_status
    results['assigned_spot_index'] = assigned_spot_index
    results['assigned_spot_mu'] = spot_mu[assigned_spot_index]
    results['assigned_spot_scan_speed_mm_s'] = spot_scan_speed_mm_s[assigned_spot_index]
    results['sample_is_transit_min_dose'] = sample_is_transit_min_dose
    results['sample_is_boundary_carryover'] = sample_is_boundary_carryover
    results['sample_is_included_filtered_stats'] = sample_is_included_filtered_stats

    bins = np.arange(HISTOGRAM_RANGE_MM[0], HISTOGRAM_RANGE_MM[1] + HISTOGRAM_BIN_STEP, HISTOGRAM_BIN_STEP)
    hist_x, _ = np.histogram(stats_diff_x, bins=bins, density=True)
    hist_y, _ = np.histogram(stats_diff_y, bins=bins, density=True)
    bin_centers = (bins[:-1] + bins[1:]) / 2

    try:
        if (np.sum(hist_x) > 0 and not np.isinf(np.sum(hist_x)) and not
                np.isnan(np.sum(hist_x))):
            params_x, _ = curve_fit(
                gaussian, bin_centers, hist_x, p0=[1, 0, 1])
        else:
            params_x = [0, 0, 0]
        if (np.sum(hist_y) > 0 and not np.isinf(np.sum(hist_y)) and not
                np.isnan(np.sum(hist_y))):
            params_y, _ = curve_fit(
                gaussian, bin_centers, hist_y, p0=[1, 0, 1])
        else:
            params_y = [0, 0, 0]
        results['hist_fit_x'] = {
            'amplitude': params_x[0],
            'mean': params_x[1],
            'stddev': params_x[2]
        }
        results['hist_fit_y'] = {
            'amplitude': params_y[0],
            'mean': params_y[1],
            'stddev': params_y[2]
        }
    except RuntimeError:
        results['hist_fit_x'] = {'amplitude': 0, 'mean': 0, 'stddev': 0}
        results['hist_fit_y'] = {'amplitude': 0, 'mean': 0, 'stddev': 0}

    # Add missing keys expected by report generator
    results['plan_positions'] = np.column_stack((interp_plan_x, interp_plan_y))
    results['log_positions'] = np.column_stack((log_x, log_y))
    stats_x = _calculate_axis_stats(stats_diff_x)
    stats_y = _calculate_axis_stats(stats_diff_y)
    results['mean_diff_x'] = stats_x['mean']
    results['mean_diff_y'] = stats_y['mean']
    results['std_diff_x'] = stats_x['std']
    results['std_diff_y'] = stats_y['std']
    results['rmse_x'] = stats_x['rmse']
    results['rmse_y'] = stats_y['rmse']
    results['max_abs_diff_x'] = stats_x['max_abs']
    results['max_abs_diff_y'] = stats_y['max_abs']
    results['p95_abs_diff_x'] = stats_x['p95_abs']
    results['p95_abs_diff_y'] = stats_y['p95_abs']
    results['time_overlap_fraction'] = overlap

    if zero_dose_filter_enabled:
        results['filtered_diff_x'] = filtered_diff_x
        results['filtered_diff_y'] = filtered_diff_y
        results['filtered_mean_diff_x'] = filtered_stats_x['mean']
        results['filtered_mean_diff_y'] = filtered_stats_y['mean']
        results['filtered_std_diff_x'] = filtered_stats_x['std']
        results['filtered_std_diff_y'] = filtered_stats_y['std']
        results['filtered_rmse_x'] = filtered_stats_x['rmse']
        results['filtered_rmse_y'] = filtered_stats_y['rmse']
        results['filtered_max_abs_diff_x'] = filtered_stats_x['max_abs']
        results['filtered_max_abs_diff_y'] = filtered_stats_y['max_abs']
        results['filtered_p95_abs_diff_x'] = filtered_stats_x['p95_abs']
        results['filtered_p95_abs_diff_y'] = filtered_stats_y['p95_abs']
        results['filtered_stats_fallback_to_raw'] = filtered_stats_fallback_to_raw
        results['num_filtered_samples'] = int(np.sum(settled_mask & (~filtered_mask)))
        results['num_included_samples'] = int(np.sum(filtered_mask))
        settled_count = int(np.sum(settled_mask))
        results['filtered_sample_fraction'] = (
            float(np.sum(settled_mask & (~filtered_mask))) / settled_count
            if settled_count
            else 0.0
        )
        sample_counts_by_spot = np.bincount(
            assigned_spot_index,
            minlength=len(plan_time_s),
        ).astype(float)
        per_sample_mu = np.divide(
            spot_mu[assigned_spot_index],
            sample_counts_by_spot[assigned_spot_index],
            out=np.zeros_like(log_time_s, dtype=float),
            where=sample_counts_by_spot[assigned_spot_index] > 0,
        )
        total_mu = float(np.sum(spot_mu))
        results['filtered_mu_fraction_estimate'] = (
            float(np.sum(per_sample_mu[settled_mask & (~filtered_mask)])) / total_mu
            if total_mu > 0
            else 0.0
        )

    return results
