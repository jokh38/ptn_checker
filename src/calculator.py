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


def _missing_required_keys(data, keys):
    for key in keys:
        if key not in data:
            return key
    return None


def _prepare_plan_and_log_arrays(plan_layer, log_data):
    plan_time_s = np.asarray(plan_layer['time_axis_s'], dtype=float)
    plan_x = np.asarray(plan_layer['trajectory_x_mm'], dtype=float)
    plan_y = np.asarray(plan_layer['trajectory_y_mm'], dtype=float)
    log_time_ms = np.asarray(log_data['time_ms'], dtype=float)
    log_time_s = (log_time_ms - float(log_time_ms[0])) / 1000.0
    log_x = np.asarray(log_data['x'], dtype=float)
    log_y = np.asarray(log_data['y'], dtype=float)
    return plan_time_s, plan_x, plan_y, log_time_s, log_x, log_y


def _interpolate_plan_series(plan_layer, log_data, plan_time_s, log_time_s):
    interp_plan_x = np.interp(log_time_s, plan_time_s, plan_layer['trajectory_x_mm'])
    interp_plan_y = np.interp(log_time_s, plan_time_s, plan_layer['trajectory_y_mm'])
    plan_cumulative_mu = _get_optional_series(
        plan_layer,
        "cumulative_mu",
        len(plan_time_s),
        "plan_layer",
    )
    interp_plan_mu = np.interp(log_time_s, plan_time_s, plan_cumulative_mu)
    log_mu = _get_optional_series(log_data, "mu", len(log_time_s), "log_data")
    return interp_plan_x, interp_plan_y, interp_plan_mu, log_mu


def _calculate_log_velocity(log_time_s, log_x, log_y):
    dx = np.diff(log_x, prepend=log_x[0])
    dy = np.diff(log_y, prepend=log_y[0])
    dt = np.diff(log_time_s, prepend=log_time_s[0])
    log_velocity_mm_s = np.zeros_like(dt)
    nonzero_dt = dt > 0
    log_velocity_mm_s[nonzero_dt] = (
        np.sqrt(dx[nonzero_dt] ** 2 + dy[nonzero_dt] ** 2) / dt[nonzero_dt]
    )
    return log_velocity_mm_s


def _normalized_spot_series(plan_layer, plan_time_s):
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

    return spot_mu, spot_is_transit_min_dose, spot_scan_speed_mm_s


def _boundary_carryover_mask(config, plan_time_s, log_time_s, assigned_spot_index, spot_is_transit_min_dose):
    sample_is_boundary_carryover = np.zeros(len(log_time_s), dtype=bool)
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
    for spot_idx in treatment_after_transit:
        spot_start_s = plan_time_s[spot_idx - 1]
        spot_samples = assigned_spot_index == spot_idx
        elapsed_s = log_time_s - spot_start_s
        if boundary_holdoff_s > 0:
            sample_is_boundary_carryover |= spot_samples & (elapsed_s < boundary_holdoff_s)
        if post_minimal_dose_boundary_s > 0:
            sample_is_boundary_carryover |= (
                spot_samples
                & (elapsed_s >= 0)
                & (elapsed_s < post_minimal_dose_boundary_s)
            )
    return sample_is_boundary_carryover


def _fit_histogram(diff):
    bins = np.arange(
        HISTOGRAM_RANGE_MM[0],
        HISTOGRAM_RANGE_MM[1] + HISTOGRAM_BIN_STEP,
        HISTOGRAM_BIN_STEP,
    )
    hist, _ = np.histogram(diff, bins=bins, density=True)
    bin_centers = (bins[:-1] + bins[1:]) / 2
    try:
        hist_sum = np.sum(hist)
        if hist_sum > 0 and not np.isinf(hist_sum) and not np.isnan(hist_sum):
            params, _ = curve_fit(gaussian, bin_centers, hist, p0=[1, 0, 1])
        else:
            params = [0, 0, 0]
    except RuntimeError:
        params = [0, 0, 0]
    return {
        'amplitude': params[0],
        'mean': params[1],
        'stddev': params[2],
    }


def _write_debug_csv(
    csv_filename,
    log_time_s,
    interp_plan_x,
    interp_plan_y,
    log_x,
    log_y,
    log_data,
    is_settling,
    log_velocity_mm_s,
    interp_plan_mu,
    log_mu,
    assigned_spot_index,
    spot_mu,
    spot_scan_speed_mm_s,
    sample_is_transit_min_dose,
    sample_is_boundary_carryover,
    sample_is_included_filtered_stats,
):
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


def _store_axis_stats(results, prefix, stats_x, stats_y):
    results[f'{prefix}mean_diff_x'] = stats_x['mean']
    results[f'{prefix}mean_diff_y'] = stats_y['mean']
    results[f'{prefix}std_diff_x'] = stats_x['std']
    results[f'{prefix}std_diff_y'] = stats_y['std']
    results[f'{prefix}rmse_x'] = stats_x['rmse']
    results[f'{prefix}rmse_y'] = stats_y['rmse']
    results[f'{prefix}max_abs_diff_x'] = stats_x['max_abs']
    results[f'{prefix}max_abs_diff_y'] = stats_y['max_abs']
    results[f'{prefix}p95_abs_diff_x'] = stats_x['p95_abs']
    results[f'{prefix}p95_abs_diff_y'] = stats_y['p95_abs']


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

    missing_plan_key = _missing_required_keys(
        plan_layer,
        ('time_axis_s', 'trajectory_x_mm', 'trajectory_y_mm'),
    )
    if missing_plan_key is not None:
        return {'error': f"Missing required plan_layer key: '{missing_plan_key}'"}

    missing_log_key = _missing_required_keys(log_data, ('time_ms', 'x', 'y'))
    if missing_log_key is not None:
        return {'error': f"Missing required log_data key: '{missing_log_key}'"}

    plan_time_s, plan_x, plan_y, log_time_s, log_x, log_y = _prepare_plan_and_log_arrays(
        plan_layer,
        log_data,
    )

    if len(plan_time_s) == 0 or len(log_time_s) == 0:
        return {'error': 'Empty data arrays'}

    interp_plan_x, interp_plan_y, interp_plan_mu, log_mu = _interpolate_plan_series(
        plan_layer,
        log_data,
        plan_time_s,
        log_time_s,
    )
    log_velocity_mm_s = _calculate_log_velocity(log_time_s, log_x, log_y)

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
    spot_mu, spot_is_transit_min_dose, spot_scan_speed_mm_s = _normalized_spot_series(
        plan_layer,
        plan_time_s,
    )

    sample_is_transit_min_dose = spot_is_transit_min_dose[assigned_spot_index]
    sample_is_boundary_carryover = _boundary_carryover_mask(
        config,
        plan_time_s,
        log_time_s,
        assigned_spot_index,
        spot_is_transit_min_dose,
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
        _write_debug_csv(
            csv_filename,
            log_time_s,
            interp_plan_x,
            interp_plan_y,
            log_x,
            log_y,
            log_data,
            is_settling,
            log_velocity_mm_s,
            interp_plan_mu,
            log_mu,
            assigned_spot_index,
            spot_mu,
            spot_scan_speed_mm_s,
            sample_is_transit_min_dose,
            sample_is_boundary_carryover,
            sample_is_included_filtered_stats,
        )

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

    results['hist_fit_x'] = _fit_histogram(stats_diff_x)
    results['hist_fit_y'] = _fit_histogram(stats_diff_y)

    # Add missing keys expected by report generator
    results['plan_positions'] = np.column_stack((interp_plan_x, interp_plan_y))
    results['log_positions'] = np.column_stack((log_x, log_y))
    stats_x = _calculate_axis_stats(stats_diff_x)
    stats_y = _calculate_axis_stats(stats_diff_y)
    _store_axis_stats(results, "", stats_x, stats_y)
    results['time_overlap_fraction'] = overlap

    if zero_dose_filter_enabled:
        results['filtered_diff_x'] = filtered_diff_x
        results['filtered_diff_y'] = filtered_diff_y
        _store_axis_stats(results, "filtered_", filtered_stats_x, filtered_stats_y)
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
