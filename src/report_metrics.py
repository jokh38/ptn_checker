import numpy as np


THRESHOLDS = {
    "mean_diff_mm": 1.0,
    "std_diff_mm": 1.5,
    "max_abs_diff_mm": 3.0,
}


def metric_key(results: dict, base_key: str, report_mode: str) -> str:
    """Resolve the raw or filtered metric key for the requested report mode."""
    if report_mode != "raw":
        filtered_key = f"filtered_{base_key}"
        if filtered_key in results:
            return filtered_key
    return base_key


def metric_value(results: dict, base_key: str, report_mode: str):
    """Return the metric value selected by ``report_mode`` with a zero fallback."""
    return results.get(metric_key(results, base_key, report_mode), 0)


def layer_passes(results: dict, report_mode: str = "raw") -> bool:
    """Check whether a single layer's metrics satisfy the report thresholds."""
    mean_ok = (
        abs(metric_value(results, "mean_diff_x", report_mode))
        <= THRESHOLDS["mean_diff_mm"]
        and abs(metric_value(results, "mean_diff_y", report_mode))
        <= THRESHOLDS["mean_diff_mm"]
    )
    std_ok = (
        metric_value(results, "std_diff_x", report_mode)
        <= THRESHOLDS["std_diff_mm"]
        and metric_value(results, "std_diff_y", report_mode)
        <= THRESHOLDS["std_diff_mm"]
    )
    max_ok = (
        metric_value(results, "max_abs_diff_x", report_mode)
        <= THRESHOLDS["max_abs_diff_mm"]
        and metric_value(results, "max_abs_diff_y", report_mode)
        <= THRESHOLDS["max_abs_diff_mm"]
    )
    return mean_ok and std_ok and max_ok


def spot_pass_summary(results: dict, report_mode: str = "raw") -> tuple[int, int]:
    """Count spots whose per-spot sample stats satisfy the layer thresholds."""
    diff_x_key = metric_key(results, "diff_x", report_mode)
    diff_y_key = metric_key(results, "diff_y", report_mode)
    assigned_spot_index = results.get("assigned_spot_index")
    if (
        diff_x_key not in results
        or diff_y_key not in results
        or assigned_spot_index is None
    ):
        return 0, 0

    diff_x = np.asarray(results[diff_x_key], dtype=float)
    diff_y = np.asarray(results[diff_y_key], dtype=float)
    assigned_spot_index = np.asarray(assigned_spot_index, dtype=int)

    if report_mode != "raw" and "sample_is_included_filtered_stats" in results:
        included_mask = np.asarray(
            results["sample_is_included_filtered_stats"], dtype=bool
        )
        if included_mask.shape[0] == assigned_spot_index.shape[0]:
            assigned_spot_index = assigned_spot_index[included_mask]

    if (
        diff_x.size == 0
        or diff_y.size == 0
        or assigned_spot_index.size == 0
        or diff_x.size != diff_y.size
        or diff_x.size != assigned_spot_index.size
    ):
        return 0, 0

    passed_spots = 0
    total_spots = 0
    for spot_index in np.unique(assigned_spot_index):
        spot_mask = assigned_spot_index == spot_index
        if not np.any(spot_mask):
            continue

        total_spots += 1
        spot_results = {
            "mean_diff_x": float(np.mean(diff_x[spot_mask])),
            "mean_diff_y": float(np.mean(diff_y[spot_mask])),
            "std_diff_x": float(np.std(diff_x[spot_mask])),
            "std_diff_y": float(np.std(diff_y[spot_mask])),
            "max_abs_diff_x": float(np.max(np.abs(diff_x[spot_mask]))),
            "max_abs_diff_y": float(np.max(np.abs(diff_y[spot_mask]))),
        }
        if layer_passes(spot_results, report_mode="raw"):
            passed_spots += 1

    return passed_spots, total_spots
