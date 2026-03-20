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
        ))
        header = (
            "log_time_s,interp_plan_x,interp_plan_y,log_x,log_y,x_raw,y_raw,"
            "layer_num,beam_on_off,is_settling,log_velocity_mm_s,interp_plan_mu,log_mu"
        )
        np.savetxt(csv_filename, data_to_save, delimiter=",", header=header, comments="")

    results['diff_x'] = diff_x
    results['diff_y'] = diff_y
    results['is_settling'] = is_settling
    results['settling_index'] = int(settling_index)
    results['settling_samples_count'] = int(np.sum(is_settling))
    results['settling_status'] = settling_status

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

    return results
