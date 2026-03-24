import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np
from scipy.stats import pearsonr

from src.report_constants import A4_FIGSIZE
from src.report_metrics import (
    THRESHOLDS,
    layer_passes as _layer_passes,
    metric_value as _metric_value,
    spot_pass_summary as _spot_pass_summary,
)


def _beam_verdict(pass_rate):
    if pass_rate == 100:
        return "PASS", "#2ecc71"
    if pass_rate >= 80:
        return "CONDITIONAL", "#e67e22"
    return "FAIL", "#e74c3c"


def _draw_analysis_info_panel(ax, layers_data, report_mode, analysis_config=None):
    cfg = analysis_config or {}
    total_samples = 0
    settled_samples = 0
    included_samples = 0
    filtered_out_samples = 0

    for layer in layers_data:
        results = layer.get("results", {})
        diff_x = results.get("diff_x")
        if diff_x is None:
            continue
        sample_count = len(np.asarray(diff_x))
        total_samples += sample_count
        settling_count = results.get("settling_samples_count", 0)
        settled_samples += (sample_count - settling_count)
        if report_mode != "raw":
            included_samples += results.get("num_included_samples", 0)
            filtered_out_samples += results.get("num_filtered_samples", 0)
        else:
            included_samples += (sample_count - settling_count)

    table_data = [
        ["\u2500 Criteria \u2500", ""],
        ["Mean |diff|", f"\u2264 {THRESHOLDS['mean_diff_mm']:.1f} mm"],
        ["Std diff", f"\u2264 {THRESHOLDS['std_diff_mm']:.1f} mm"],
        ["Max |diff|", f"\u2264 {THRESHOLDS['max_abs_diff_mm']:.1f} mm"],
    ]
    settle_thresh = cfg.get("SETTLING_THRESHOLD_MM")
    settle_consec = cfg.get("SETTLING_CONSECUTIVE_SAMPLES")
    settle_window = cfg.get("SETTLING_WINDOW_SAMPLES")
    if settle_thresh is not None:
        table_data.append(["\u2500 Settling \u2500", ""])
        table_data.append(["Threshold", f"{settle_thresh:.2f} mm"])
        if settle_consec is not None:
            table_data.append(["Consec. samples", f"{int(settle_consec)}"])
        if settle_window is not None:
            table_data.append(["Window samples", f"{int(settle_window)}"])

    zd_enabled = cfg.get("ZERO_DOSE_FILTER_ENABLED")
    if zd_enabled is not None:
        table_data.append(["\u2500 Zero-dose \u2500", ""])
        table_data.append(["Filter", "Enabled" if zd_enabled else "Disabled"])
        if zd_enabled:
            zd_max_mu = cfg.get("ZERO_DOSE_MAX_MU")
            if zd_max_mu is not None:
                table_data.append(["Max MU", f"{zd_max_mu:.4f}"])
            zd_holdoff = cfg.get("ZERO_DOSE_BOUNDARY_HOLDOFF_S")
            if zd_holdoff is not None:
                table_data.append(["Boundary holdoff", f"{zd_holdoff:.4f} s"])
            zd_report = cfg.get("ZERO_DOSE_REPORT_MODE")
            if zd_report is not None:
                table_data.append(["Report mode", str(zd_report)])

    table_data.extend([
        ["\u2500 Samples \u2500", ""],
        ["Total", f"{total_samples:,}"],
        ["After settling", f"{settled_samples:,}"],
    ])
    if report_mode != "raw":
        table_data.append(["Filtered out", f"{filtered_out_samples:,}"])
    table_data.append(["Included", f"{included_samples:,}"])

    ax.set_title("Analysis Info", fontsize=8, fontweight="bold", pad=4)
    tbl = ax.table(
        cellText=table_data,
        colLabels=["Parameter", "Value"],
        loc="upper center",
        cellLoc="left",
        colWidths=[0.55, 0.45],
    )
    tbl.auto_set_font_size(False)
    num_rows = len(table_data)
    tbl_fontsize = 6.0 if num_rows > 14 else 6.5
    tbl.set_fontsize(tbl_fontsize)
    row_scale = min(1.4, max(0.7, 12.0 / (num_rows + 1)))
    tbl.scale(1.0, row_scale)

    for col_idx in range(2):
        tbl[0, col_idx].set_facecolor("#34495e")
        tbl[0, col_idx].set_text_props(color="white", fontweight="bold", fontsize=tbl_fontsize)

    for row_idx, row in enumerate(table_data, start=1):
        if row[0].startswith("\u2500"):
            for col_idx in range(2):
                tbl[row_idx, col_idx].set_facecolor("#5d6d7e")
                tbl[row_idx, col_idx].set_text_props(
                    color="white",
                    fontweight="bold" if col_idx == 0 else None,
                    fontsize=tbl_fontsize,
                )
        else:
            tbl[row_idx, 0].set_text_props(fontweight="bold")
            tbl[row_idx, 0].set_facecolor("#f8f8f8")
            tbl[row_idx, 1].set_facecolor("white")


def _gamma_percent(value):
    numeric = float(value)
    return numeric * 100.0 if numeric <= 1.0 else numeric


def _style_header_table(tbl, *, header_rows=None, fontsize=6.0):
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(fontsize)
    for (row_idx, _), cell in tbl.get_celld().items():
        cell.PAD = 0.02
        cell.set_linewidth(0.8)
        cell.set_edgecolor("#34495e")
        if header_rows and row_idx in header_rows:
            cell.set_facecolor("#34495e")
            cell.set_text_props(color="white", fontweight="bold", va="center")
        else:
            cell.set_facecolor("white")
            cell.set_text_props(va="center")


def _gamma_beam_verdict(pass_rate_percent):
    if pass_rate_percent >= 95.0:
        return "PASS", "#2ecc71"
    if pass_rate_percent >= 80.0:
        return "CONDITIONAL", "#e67e22"
    return "FAIL", "#e74c3c"


def _collect_point_gamma_beam_metrics(layers_data):
    layer_labels = []
    layer_pass_rates = []
    pass_flags = []
    gamma_means = []
    gamma_maxes = []
    evaluated_points = []
    position_error_means = []
    count_error_means = []
    weighted_pass_total = 0.0
    weighted_gamma_mean_total = 0.0
    weighted_position_error_total = 0.0
    weighted_count_error_total = 0.0
    evaluated_point_total = 0

    for layer in layers_data:
        results = layer.get("results", {})
        raw_idx = layer.get("layer_index", 0)
        layer_labels.append(str(int(raw_idx) // 2 + 1))

        pass_rate_percent = _gamma_percent(results.get("pass_rate", 0.0))
        evaluated_point_count = int(results.get("evaluated_point_count", 0))
        gamma_mean = float(results.get("gamma_mean", 0.0))
        gamma_max = float(results.get("gamma_max", 0.0))
        position_error_mean_mm = float(results.get("position_error_mean_mm", 0.0))
        count_error_mean = float(results.get("count_error_mean", 0.0))

        layer_pass_rates.append(pass_rate_percent)
        pass_flags.append(pass_rate_percent < 95.0)
        gamma_means.append(gamma_mean)
        gamma_maxes.append(gamma_max)
        evaluated_points.append(evaluated_point_count)
        position_error_means.append(position_error_mean_mm)
        count_error_means.append(count_error_mean)

        weighted_pass_total += pass_rate_percent * evaluated_point_count
        weighted_gamma_mean_total += gamma_mean * evaluated_point_count
        weighted_position_error_total += position_error_mean_mm * evaluated_point_count
        weighted_count_error_total += count_error_mean * evaluated_point_count
        evaluated_point_total += evaluated_point_count

    beam_pass_rate = (
        float(weighted_pass_total / evaluated_point_total)
        if evaluated_point_total > 0
        else 0.0
    )
    beam_gamma_mean = (
        float(weighted_gamma_mean_total / evaluated_point_total)
        if evaluated_point_total > 0
        else 0.0
    )
    beam_position_error_mean = (
        float(weighted_position_error_total / evaluated_point_total)
        if evaluated_point_total > 0
        else 0.0
    )
    beam_count_error_mean = (
        float(weighted_count_error_total / evaluated_point_total)
        if evaluated_point_total > 0
        else 0.0
    )
    return {
        "layer_labels": layer_labels,
        "layer_pass_rates": layer_pass_rates,
        "pass_flags": pass_flags,
        "gamma_means": gamma_means,
        "gamma_maxes": gamma_maxes,
        "evaluated_points": evaluated_points,
        "position_error_means": position_error_means,
        "count_error_means": count_error_means,
        "beam_pass_rate": beam_pass_rate,
        "beam_gamma_mean": beam_gamma_mean,
        "beam_gamma_max": float(max(gamma_maxes)) if gamma_maxes else 0.0,
        "beam_position_error_mean": beam_position_error_mean,
        "beam_count_error_mean": beam_count_error_mean,
        "evaluated_point_total": evaluated_point_total,
    }


def _draw_point_gamma_analysis_info_panel(
    ax,
    analysis_config=None,
):
    cfg = analysis_config or {}
    ax.set_title("Config / Info", fontsize=8, fontweight="bold", pad=0, y=0.95)
    tbl = ax.table(
        cellText=[[
            f"{cfg.get('GAMMA_DISTANCE_MM_THRESHOLD', 0):.1f} mm",
            f"{cfg.get('GAMMA_FLUENCE_PERCENT_THRESHOLD', 0):.1f}% of peak plan count",
            f"{cfg.get('GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF', 0):.1f}% of peak plan count",
        ]],
        colLabels=["Distance to agreement", "Count threshold", "Lower fluence cutoff"],
        bbox=[0.0, 0.18, 1.0, 0.70],
        cellLoc="center",
        colWidths=[0.30, 0.35, 0.35],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(6.3)
    tbl.scale(1.0, 1.05)

    for col_idx in range(3):
        tbl[0, col_idx].set_facecolor("#34495e")
        tbl[0, col_idx].set_text_props(color="white", fontweight="bold", fontsize=6.3)
        tbl[1, col_idx].set_facecolor("white")


def _draw_position_summary_table(
    ax,
    *,
    global_mean_x,
    global_mean_y,
    global_std_x,
    global_std_y,
    global_rmse_x,
    global_rmse_y,
    global_max_x,
    global_max_y,
    global_p95_x,
    global_p95_y,
    similarity_str,
    include_radial=False,
    radial_mean=0,
    radial_rmse=0,
    radial_max=0,
    radial_p95=0,
):
    thr_mean = THRESHOLDS["mean_diff_mm"]
    thr_std = THRESHOLDS["std_diff_mm"]
    thr_max = THRESHOLDS["max_abs_diff_mm"]
    ax.axis("off")
    col_labels = [
        "",
        f"Mean (\u2264{thr_mean})",
        f"Std (\u2264{thr_std})",
        "RMSE (mm)",
        f"Max (\u2264{thr_max})",
        "P95 (mm)",
        "Similarity",
    ]
    cell_text = [
        ["X", f"{global_mean_x:+.3f}", f"{global_std_x:.3f}", f"{global_rmse_x:.3f}", f"{global_max_x:.3f}", f"{global_p95_x:.3f}", similarity_str],
        ["Y", f"{global_mean_y:+.3f}", f"{global_std_y:.3f}", f"{global_rmse_y:.3f}", f"{global_max_y:.3f}", f"{global_p95_y:.3f}", ""],
    ]
    row_label_colors = [(1, "#3498db"), (2, "#e67e22")]
    color_row_vals = [
        (abs(global_mean_x), global_std_x, global_rmse_x, global_max_x, global_p95_x),
        (abs(global_mean_y), global_std_y, global_rmse_y, global_max_y, global_p95_y),
    ]
    if include_radial:
        cell_text.append(
            ["Radial", f"{radial_mean:.3f}", "", f"{radial_rmse:.3f}", f"{radial_max:.3f}", f"{radial_p95:.3f}", ""]
        )
        row_label_colors.append((3, "#8e44ad"))
        color_row_vals.append((radial_mean, 0, radial_rmse, radial_max, radial_p95))

    metrics_table = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
        colWidths=[0.12, 0.15, 0.15, 0.14, 0.14, 0.14, 0.16],
    )
    metrics_table.auto_set_font_size(False)
    metrics_table.set_fontsize(6.5)
    metrics_table.scale(1.0, 1.18 if include_radial else 1.15)
    for idx in range(len(col_labels)):
        metrics_table[0, idx].set_facecolor("#34495e")
        metrics_table[0, idx].set_text_props(color="white", fontweight="bold", va="center")
    for row_idx, color in row_label_colors:
        metrics_table[row_idx, 0].set_facecolor(color)
        metrics_table[row_idx, 0].set_text_props(color="white", fontweight="bold", va="center")
    for (_, _), cell in metrics_table.get_celld().items():
        cell.set_text_props(va="center")
        cell.PAD = 0.02

    for row_idx, row_vals in enumerate(color_row_vals, start=1):
        for col_idx, threshold in {1: thr_mean, 2: thr_std, 4: thr_max}.items():
            ratio = row_vals[col_idx - 1] / threshold if threshold > 0 else 0
            metrics_table[row_idx, col_idx].set_facecolor(
                "#d5f5e3" if ratio <= 0.5 else "#fdebd0" if ratio <= 1.0 else "#fadbd8"
            )


def _draw_gamma_summary_table(
    ax,
    *,
    num_layers,
    beam_pass_rate,
    beam_gamma_mean,
    beam_gamma_max,
    evaluated_point_total,
    beam_position_error_mean,
    beam_count_error_mean,
):
    ax.axis("off")
    ax.set_title("Gamma Summary", fontsize=8, fontweight="bold", pad=0, y=0.95)
    tbl = ax.table(
        cellText=[[
            f"{beam_pass_rate:.1f}%",
            f"{beam_gamma_mean:.3f}",
            f"{beam_gamma_max:.3f}",
            f"{evaluated_point_total:,}",
            f"{beam_position_error_mean:.3f} mm",
            f"{beam_count_error_mean:.3g}",
            f"{num_layers}",
        ]],
        colLabels=[
            "Gamma pass (%)",
            "Gamma mean",
            "Gamma max",
            "Evaluated points",
            "Pos err mean (mm)",
            "Count err mean",
            "Layers",
        ],
        loc="center",
        cellLoc="center",
        colWidths=[0.15, 0.125, 0.125, 0.165, 0.18, 0.16, 0.095],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(6.1)
    tbl.scale(1.0, 1.12)
    for col_idx in range(7):
        tbl[0, col_idx].set_facecolor("#34495e")
        tbl[0, col_idx].set_text_props(color="white", fontweight="bold", fontsize=6.1)
        tbl[1, col_idx].set_facecolor("white")


def _layer_flag_codes(flag_rows, num_layers):
    if num_layers <= 0:
        return [], []
    priority = [
        ("Fail", "FAIL", 4),
        ("Settle", "NS", 3),
        ("Overlap", "OV", 2),
        ("Fallback", "FB", 1),
    ]
    codes = []
    values = []
    for layer_idx in range(num_layers):
        code = ""
        value = 0
        for row_name, row_code, row_value in priority:
            row = flag_rows.get(row_name) if flag_rows else None
            if row is not None and layer_idx < len(row) and bool(row[layer_idx]):
                code = row_code
                value = row_value
                break
        codes.append(code)
        values.append(value)
    return codes, values


def _draw_layer_heatmap(
    fig,
    title_ax,
    group_header_ax,
    metric_header_ax,
    side_header_ax,
    ax,
    heatmap_values,
    layer_labels,
    metric_labels,
    flag_rows=None,
    flag_ax=None,
    flag_legend_ax=None,
    cbar_ax=None,
    side_values=None,
    side_label=None,
    side_cmap=None,
    side_vmin=None,
    side_vmax=None,
    side_text_labels=None,
):
    heatmap_values = np.asarray(heatmap_values, dtype=float)
    num_metrics, num_layers = heatmap_values.shape if heatmap_values.size else (0, 0)

    title_ax.axis("off")
    title_ax.text(0.5, 0.55, "Layer Heatmap", ha="center", va="center", fontsize=9, fontweight="bold", transform=title_ax.transAxes)
    group_header_ax.axis("off")
    metric_header_ax.axis("off")
    side_header_ax.axis("off")
    if num_metrics > 0:
        metric_table = metric_header_ax.table(
            cellText=[metric_labels],
            cellLoc="center",
            colWidths=[1.0 / num_metrics] * num_metrics,
            bbox=[0.0, 0.0, 1.0, 1.0],
        )
        _style_header_table(metric_table, fontsize=6.0)

        if num_metrics >= 6:
            col_widths = [3.0 / num_metrics, 3.0 / num_metrics]
            group_labels = ["X", "Y"]
            if num_metrics >= 7:
                group_labels.append("Gamma")
                remaining = num_metrics - 6
                col_widths.append(remaining / num_metrics)
            group_table = group_header_ax.table(
                cellText=[group_labels],
                cellLoc="center",
                colWidths=col_widths,
                bbox=[0.0, 0.0, 1.0, 1.0],
            )
            _style_header_table(group_table, header_rows={0}, fontsize=6.0)

    side_header = ""
    if side_values is not None:
        side_header = side_label or ""
    elif flag_rows:
        side_header = "Flag"
    if side_header:
        side_table = side_header_ax.table(
            cellText=[[side_header]],
            cellLoc="center",
            colWidths=[1.0],
            bbox=[0.0, 0.0, 1.0, 1.0],
        )
        _style_header_table(side_table, header_rows={0}, fontsize=6.0)

    image = ax.imshow(
        heatmap_values.T,
        aspect="auto",
        interpolation="nearest",
        cmap=plt.cm.RdYlGn_r,
        norm=Normalize(vmin=0, vmax=THRESHOLDS["max_abs_diff_mm"]),
        origin="upper",
    )
    ax.set_yticks(np.arange(num_layers))
    ax.set_xticks(np.arange(num_metrics))
    ax.set_xticklabels([])
    if num_metrics >= 6:
        ax.axvline(x=2.5, color="white", linewidth=2.5, zorder=5)
    if num_layers > 25:
        tick_step = max(1, int(np.ceil(num_layers / 25)))
        tick_positions = np.arange(0, num_layers, tick_step)
        ax.set_yticks(tick_positions)
        ax.set_yticklabels([layer_labels[i] for i in tick_positions], fontsize=5)
    else:
        ax.set_yticklabels(layer_labels, fontsize=6)
    ax.set_xlabel("Metric", fontsize=7)
    ax.set_ylabel("Layer", fontsize=7)
    ax.tick_params(axis="x", length=0, pad=1, labelsize=6)
    ax.tick_params(axis="y", labelsize=6)
    cbar = fig.colorbar(
        image,
        cax=cbar_ax,
        ax=None if cbar_ax is not None else ax,
        orientation="horizontal",
        fraction=0.08 if cbar_ax is None else None,
        pad=0.16 if cbar_ax is None else None,
    )
    cbar.ax.tick_params(labelsize=5)
    cbar.set_label("Error severity (mm)", fontsize=6)

    flag_image = None
    if side_values is not None:
        side_array = np.asarray(side_values, dtype=float).reshape(num_layers, 1)
        if flag_ax is None:
            flag_ax = ax.inset_axes([1.02, 0.0, 0.12, 1.0])
        flag_image = flag_ax.imshow(
            side_array,
            aspect="auto",
            interpolation="nearest",
            cmap=side_cmap or plt.cm.RdYlGn,
            vmin=0 if side_vmin is None else side_vmin,
            vmax=100 if side_vmax is None else side_vmax,
            origin="upper",
        )
        flag_ax.set_xticks([0])
        flag_ax.set_xticklabels([""], fontsize=6)
        if num_layers > 25:
            tick_step = max(1, int(np.ceil(num_layers / 25)))
            flag_ax.set_yticks(np.arange(0, num_layers, tick_step))
            flag_ax.set_yticklabels([])
        else:
            flag_ax.set_yticks(np.arange(num_layers))
            flag_ax.set_yticklabels([])
        flag_ax.tick_params(axis="x", length=0, pad=1)
        flag_ax.tick_params(axis="y", length=0)
        rendered_side_labels = side_text_labels or [
            f"{float(value):.0f}" if np.isfinite(value) else ""
            for value in np.ravel(side_array)
        ]
        for layer_idx, text_label in enumerate(rendered_side_labels):
            if text_label:
                flag_ax.text(0, layer_idx, text_label, ha="center", va="center", fontsize=5.5, fontweight="bold", color="black")
        if flag_legend_ax is not None:
            flag_legend_ax.axis("off")
    elif flag_rows:
        flag_codes, flag_values = _layer_flag_codes(flag_rows, num_layers)
        if flag_ax is None:
            flag_ax = ax.inset_axes([1.02, 0.0, 0.12, 1.0])
        flag_image = flag_ax.imshow(
            np.asarray(flag_values, dtype=float).reshape(num_layers, 1),
            aspect="auto",
            interpolation="nearest",
            cmap=plt.cm.YlOrRd,
            vmin=0,
            vmax=4,
            origin="upper",
        )
        flag_ax.set_xticks([0])
        flag_ax.set_xticklabels([""], fontsize=6)
        if num_layers > 25:
            tick_step = max(1, int(np.ceil(num_layers / 25)))
            flag_ax.set_yticks(np.arange(0, num_layers, tick_step))
            flag_ax.set_yticklabels([])
        else:
            flag_ax.set_yticks(np.arange(num_layers))
            flag_ax.set_yticklabels([])
        flag_ax.tick_params(axis="x", length=0, pad=1)
        flag_ax.tick_params(axis="y", length=0)
        for layer_idx, code in enumerate(flag_codes):
            if code:
                flag_ax.text(0, layer_idx, code, ha="center", va="center", fontsize=6, fontweight="bold", color="black")
        legend_target_ax = flag_legend_ax or flag_ax
        if flag_legend_ax is not None:
            flag_legend_ax.axis("off")
        legend_target_ax.text(
            0.5,
            0.5 if flag_legend_ax is not None else -0.10,
            "FAIL = layer fail  |  FB = fallback to raw  |  NS = never settled  |  OV = low overlap",
            ha="center",
            va="center",
            fontsize=4.5,
            transform=legend_target_ax.transAxes,
            clip_on=flag_legend_ax is None,
        )
    return image, flag_image


def _collect_beam_metrics(layers_data, report_mode):
    metrics = {name: [] for name in (
        "mean_x", "mean_y", "std_x", "std_y", "rmse_x", "rmse_y", "max_x", "max_y", "p95_x", "p95_y"
    )}
    all_plan_pos = []
    all_log_pos = []
    pass_flags = []
    layer_labels = []
    passed_spots = 0
    total_spots = 0
    for layer in layers_data:
        results = layer.get("results", {})
        raw_idx = layer.get("layer_index", 0)
        layer_labels.append(str(int(raw_idx) // 2 + 1))
        metrics["mean_x"].append(_metric_value(results, "mean_diff_x", report_mode))
        metrics["mean_y"].append(_metric_value(results, "mean_diff_y", report_mode))
        metrics["std_x"].append(_metric_value(results, "std_diff_x", report_mode))
        metrics["std_y"].append(_metric_value(results, "std_diff_y", report_mode))
        metrics["rmse_x"].append(_metric_value(results, "rmse_x", report_mode))
        metrics["rmse_y"].append(_metric_value(results, "rmse_y", report_mode))
        metrics["max_x"].append(_metric_value(results, "max_abs_diff_x", report_mode))
        metrics["max_y"].append(_metric_value(results, "max_abs_diff_y", report_mode))
        metrics["p95_x"].append(_metric_value(results, "p95_abs_diff_x", report_mode))
        metrics["p95_y"].append(_metric_value(results, "p95_abs_diff_y", report_mode))
        plan_pos = results.get("plan_positions")
        log_pos = results.get("log_positions")
        if plan_pos is not None:
            all_plan_pos.append(plan_pos)
        if log_pos is not None:
            all_log_pos.append(log_pos)
        pass_flags.append(_layer_passes(results, report_mode=report_mode))
        layer_passed_spots, layer_total_spots = _spot_pass_summary(results, report_mode=report_mode)
        passed_spots += layer_passed_spots
        total_spots += layer_total_spots
    return metrics, all_plan_pos, all_log_pos, pass_flags, layer_labels, passed_spots, total_spots


def build_summary_skeleton(
    *,
    beam_name,
    verdict_text,
    verdict_color,
    subtitle_line,
    extra_subtitle=None,
    extra_subtitle_bold=False,
    has_top_summary=False,
    top_summary_rows=0,
    top_summary_bounds=(0.06, 0.94, 0.785, 0.9),
    top_summary_hspace=0.3,
    middle_width_ratios=(0.9, 1.3),
    middle_bounds=(0.06, 0.97, 0.12, 0.78),
    left_height_ratios=(0.04, 0.08, 0.76, 0.06, 0.04),
    left_hspace=0.08,
    right_height_ratios=(0.04, 0.03, 0.03, 0.785, 0.025, 0.04),
    right_hspace=0.01,
    bottom_width_ratios=(0.6, 1.0),
    bottom_bounds=(0.06, 0.97, 0.03, 0.10),
    bottom_wspace=0.10,
):
    """Build common page skeleton used by both summary page types.

    Returns a dict of named axes:
      fig, trend_title, trend, heatmap_title, heatmap_group_header,
      heatmap_metric_header, heatmap_side_header,
      heatmap, heatmap_flags, heatmap_cbar, heatmap_flag_legend,
      bottom_left, bottom_right (or bottom if single-column),
      top_summary_0..N (if has_top_summary).
    """
    fig = plt.figure(figsize=A4_FIGSIZE)

    # -- Header --------------------------------------------------------
    fig.text(0.50, 0.97, beam_name, ha="center", va="top", fontsize=16, fontweight="bold")
    fig.text(
        0.95, 0.97, verdict_text,
        ha="right", va="top", fontsize=10, fontweight="bold", color="white",
        bbox=dict(boxstyle="round,pad=0.3", facecolor=verdict_color, edgecolor="none"),
    )
    fig.text(0.50, 0.935, subtitle_line, ha="center", va="top", fontsize=8, color="#555555")
    if extra_subtitle is not None:
        kwargs = {"fontweight": "bold"} if extra_subtitle_bold else {}
        fig.text(
            0.50, 0.918, extra_subtitle,
            ha="center", va="top", fontsize=7, color="#555555", **kwargs,
        )

    axes = {"fig": fig}

    # -- Top summary tables (optional) ---------------------------------
    if has_top_summary and top_summary_rows > 0:
        ts_left, ts_right, ts_bottom, ts_top = top_summary_bounds
        top_gs = fig.add_gridspec(
            top_summary_rows, 1,
            left=ts_left, right=ts_right, bottom=ts_bottom, top=ts_top,
            hspace=top_summary_hspace,
        )
        for row_idx in range(top_summary_rows):
            axes[f"top_summary_{row_idx}"] = fig.add_subplot(top_gs[row_idx, 0])

    # -- Middle section ------------------------------------------------
    m_left, m_right, m_bottom, m_top = middle_bounds
    middle_gs = fig.add_gridspec(
        1, 2, left=m_left, right=m_right, bottom=m_bottom, top=m_top,
        wspace=0.16, width_ratios=list(middle_width_ratios),
    )

    # Left panel (trend)
    left_gs = middle_gs[0, 0].subgridspec(
        5, 1, height_ratios=list(left_height_ratios), hspace=left_hspace,
    )
    ax_trend_title = fig.add_subplot(left_gs[0, 0])
    ax_trend_title.axis("off")
    ax_trend_title.text(
        0.5, 0.3, "Layer Trend", ha="center", va="center",
        fontsize=9, fontweight="bold", transform=ax_trend_title.transAxes,
    )
    ax_trend = fig.add_subplot(left_gs[1:, 0])
    axes["trend_title"] = ax_trend_title
    axes["trend"] = ax_trend

    # Right panel (heatmap)
    right_gs = middle_gs[0, 1].subgridspec(
        6, 2,
        height_ratios=list(right_height_ratios),
        width_ratios=[0.90, 0.10],
        hspace=right_hspace,
        wspace=0.08,
    )
    ax_heatmap_title = fig.add_subplot(right_gs[0, :])
    ax_heatmap_group_header = fig.add_subplot(right_gs[1, 0])
    ax_heatmap_metric_header = fig.add_subplot(right_gs[2, 0])
    ax_heatmap_side_header = fig.add_subplot(right_gs[1:3, 1])
    ax_heatmap = fig.add_subplot(right_gs[3, 0])
    ax_heatmap_flags = fig.add_subplot(right_gs[3, 1])
    ax_heatmap_cbar = fig.add_subplot(right_gs[4, :])
    ax_heatmap_flag_legend = fig.add_subplot(right_gs[5, :])

    group_header_pos = ax_heatmap_group_header.get_position()
    metric_header_pos = ax_heatmap_metric_header.get_position()
    tightened_metric_top = group_header_pos.y0 - 0.0002
    if tightened_metric_top > metric_header_pos.y0:
        ax_heatmap_metric_header.set_position([
            metric_header_pos.x0,
            metric_header_pos.y0,
            metric_header_pos.width,
            tightened_metric_top - metric_header_pos.y0,
        ])

    # Nudge: tighten header-to-heatmap gap
    heatmap_pos = ax_heatmap.get_position()
    header_pos = ax_heatmap_metric_header.get_position()
    tightened_heatmap_top = header_pos.y0 - 0.0002
    if tightened_heatmap_top > heatmap_pos.y1:
        ax_heatmap.set_position([
            heatmap_pos.x0, heatmap_pos.y0,
            heatmap_pos.width, tightened_heatmap_top - heatmap_pos.y0,
        ])
        flag_pos = ax_heatmap_flags.get_position()
        ax_heatmap_flags.set_position([
            flag_pos.x0, flag_pos.y0,
            flag_pos.width, tightened_heatmap_top - flag_pos.y0,
        ])
    for axis in (ax_heatmap_cbar, ax_heatmap_flag_legend):
        pos = axis.get_position()
        axis.set_position([pos.x0, pos.y0 - 0.006, pos.width, pos.height])

    axes["heatmap_title"] = ax_heatmap_title
    axes["heatmap_group_header"] = ax_heatmap_group_header
    axes["heatmap_metric_header"] = ax_heatmap_metric_header
    axes["heatmap_side_header"] = ax_heatmap_side_header
    axes["heatmap"] = ax_heatmap
    axes["heatmap_flags"] = ax_heatmap_flags
    axes["heatmap_cbar"] = ax_heatmap_cbar
    axes["heatmap_flag_legend"] = ax_heatmap_flag_legend

    # -- Bottom section ------------------------------------------------
    b_left, b_right, b_bottom, b_top = bottom_bounds
    if bottom_width_ratios is not None:
        bottom_gs = fig.add_gridspec(
            1, 2, left=b_left, right=b_right, bottom=b_bottom, top=b_top,
            wspace=bottom_wspace, width_ratios=list(bottom_width_ratios),
        )
        axes["bottom_left"] = fig.add_subplot(bottom_gs[0, 0])
        axes["bottom_right"] = fig.add_subplot(bottom_gs[0, 1])
    else:
        bottom_gs = fig.add_gridspec(
            1, 1, left=b_left, right=b_right, bottom=b_bottom, top=b_top,
        )
        axes["bottom"] = fig.add_subplot(bottom_gs[0, 0])

    return axes


def _generate_summary_page(
    beam_name,
    beam_data,
    patient_id="",
    patient_name="",
    report_mode="raw",
    analysis_config=None,
):
    from datetime import date as _date

    layers_data = beam_data["layers"]
    num_layers = len(layers_data)
    metrics, all_plan_pos, all_log_pos, pass_flags, layer_labels, num_pass, total_spots = _collect_beam_metrics(layers_data, report_mode)
    mean_x_all = metrics["mean_x"]
    mean_y_all = metrics["mean_y"]
    std_x_all = metrics["std_x"]
    std_y_all = metrics["std_y"]
    rmse_x_all = metrics["rmse_x"]
    rmse_y_all = metrics["rmse_y"]
    max_x_all = metrics["max_x"]
    max_y_all = metrics["max_y"]
    p95_x_all = metrics["p95_x"]
    p95_y_all = metrics["p95_y"]
    pass_rate = num_pass / total_spots * 100 if total_spots > 0 else 0

    similarity_str = "N/A"
    if all_plan_pos and all_log_pos:
        plan_concat = np.vstack(all_plan_pos).ravel()
        log_concat = np.vstack(all_log_pos).ravel()
        if len(plan_concat) == len(log_concat) and len(plan_concat) > 1:
            corr, _ = pearsonr(plan_concat, log_concat)
            similarity_str = f"{corr:.6f}"

    verdict, pass_color = _beam_verdict(pass_rate)
    global_mean_x = np.mean(mean_x_all) if mean_x_all else 0
    global_mean_y = np.mean(mean_y_all) if mean_y_all else 0
    global_std_x = np.mean(std_x_all) if std_x_all else 0
    global_std_y = np.mean(std_y_all) if std_y_all else 0
    global_rmse_x = np.mean(rmse_x_all) if rmse_x_all else 0
    global_rmse_y = np.mean(rmse_y_all) if rmse_y_all else 0
    global_max_x = max(max_x_all) if max_x_all else 0
    global_max_y = max(max_y_all) if max_y_all else 0
    global_p95_x = np.mean(p95_x_all) if p95_x_all else 0
    global_p95_y = np.mean(p95_y_all) if p95_y_all else 0

    radial_means = np.sqrt(np.array(mean_x_all) ** 2 + np.array(mean_y_all) ** 2)
    radial_per_layer = np.sqrt(np.array(rmse_x_all) ** 2 + np.array(rmse_y_all) ** 2)
    global_radial_mean = float(np.mean(radial_means)) if len(radial_means) else 0
    global_radial_max = float(np.max(radial_means)) if len(radial_means) else 0
    global_radial_p95 = float(np.percentile(radial_per_layer, 95)) if len(radial_per_layer) else 0
    global_radial_rmse = float(np.mean(radial_per_layer)) if len(radial_per_layer) else 0

    extra_subtitle = (
        f"Zero-dose filter active: {report_mode} metrics shown"
        if report_mode != "raw"
        else None
    )
    axes = build_summary_skeleton(
        beam_name=beam_name,
        verdict_text=f"{verdict} {num_pass}/{total_spots} ({pass_rate:.0f}%)",
        verdict_color=pass_color,
        subtitle_line=f"Patient ID: {patient_id}    |    Name: {patient_name}    |    Date: {_date.today().isoformat()}    |    Layers: {num_layers}",
        extra_subtitle=extra_subtitle,
        has_top_summary=True,
        top_summary_rows=1,
        top_summary_bounds=(0.06, 0.94, 0.79, 0.89),
        middle_width_ratios=(0.9, 1.3),
        middle_bounds=(0.06, 0.97, 0.12, 0.78),
        left_height_ratios=(0.04, 0.08, 0.76, 0.06, 0.04),
        left_hspace=0.08,
        right_height_ratios=(0.04, 0.03, 0.03, 0.785, 0.025, 0.04),
        right_hspace=0.01,
        bottom_width_ratios=(0.6, 1.0),
        bottom_bounds=(0.06, 0.97, 0.03, 0.10),
        bottom_wspace=0.10,
    )
    fig = axes["fig"]

    # Top summary: position metrics with radial row
    _draw_position_summary_table(
        axes["top_summary_0"],
        global_mean_x=global_mean_x,
        global_mean_y=global_mean_y,
        global_std_x=global_std_x,
        global_std_y=global_std_y,
        global_rmse_x=global_rmse_x,
        global_rmse_y=global_rmse_y,
        global_max_x=global_max_x,
        global_max_y=global_max_y,
        global_p95_x=global_p95_x,
        global_p95_y=global_p95_y,
        similarity_str=similarity_str,
        include_radial=True,
        radial_mean=global_radial_mean,
        radial_rmse=global_radial_rmse,
        radial_max=global_radial_max,
        radial_p95=global_radial_p95,
    )

    # Left panel: layer trend plot
    ax_err = axes["trend"]
    layer_idx = np.arange(1, num_layers + 1)
    worst_axis_error = np.maximum(np.array(max_x_all), np.array(max_y_all))
    y_x = layer_idx - 0.16
    y_y = layer_idx + 0.16
    ax_err.errorbar(mean_x_all, y_x, xerr=std_x_all, fmt="o", markersize=3.5, linewidth=1.0, capsize=2.5, color="#1f77b4", ecolor="#1f77b4", label="X mean \u00b1 std", zorder=3)
    ax_err.errorbar(mean_y_all, y_y, xerr=std_y_all, fmt="s", markersize=3.2, linewidth=1.0, capsize=2.5, color="#ff7f0e", ecolor="#ff7f0e", label="Y mean \u00b1 std", zorder=3)
    ax_err.scatter(mean_x_all, y_x, c=["#2ecc71" if passed else "#e74c3c" for passed in pass_flags], s=14, zorder=4, edgecolors="white", linewidths=0.3)
    ax_err.scatter(mean_y_all, y_y, c=["#2ecc71" if passed else "#e74c3c" for passed in pass_flags], s=14, zorder=4, edgecolors="white", linewidths=0.3, marker="s")
    ax_err.axvspan(-THRESHOLDS["mean_diff_mm"], THRESHOLDS["mean_diff_mm"],
                   alpha=0.12, color="#2ecc71", zorder=1, label=f"\u00b1{THRESHOLDS['mean_diff_mm']} mm mean target")
    for x_pos, style, color in (
        (0, "-", "#7f8c8d"),
        (THRESHOLDS["mean_diff_mm"], "--", "#95a5a6"),
        (-THRESHOLDS["mean_diff_mm"], "--", "#95a5a6"),
    ):
        ax_err.axvline(x_pos, linestyle=style, linewidth=0.8 if style != "-" else 0.9, color=color, alpha=0.8)
    ax_err.set_xlabel("Deviation (mm)", fontsize=7)
    ax_err.set_ylabel("Layer", fontsize=7)
    ax_err.set_yticks(layer_idx)
    ax_err.set_yticklabels(layer_labels)
    ax_err.set_ylim(num_layers + 0.6, 0.4)
    ax_err.tick_params(labelsize=6)
    ax_err.grid(True, alpha=0.3, axis="x")
    if num_layers > 25:
        ax_err.tick_params(axis="y", labelsize=4)
    all_devs = np.concatenate([np.array(mean_x_all) - np.array(std_x_all), np.array(mean_x_all) + np.array(std_x_all),
                               np.array(mean_y_all) - np.array(std_y_all), np.array(mean_y_all) + np.array(std_y_all)])
    dev_min = min(float(all_devs.min()), -THRESHOLDS["mean_diff_mm"])
    dev_max = max(float(all_devs.max()), THRESHOLDS["mean_diff_mm"])
    margin = max(0.2, (dev_max - dev_min) * 0.1)
    ax_err.set_xlim(dev_min - margin, dev_max + margin)
    ax_err.legend(fontsize=5, loc="upper left")

    # Right panel: layer heatmap
    fallback_flags = []
    never_settled_flags = []
    low_overlap_flags = []
    for layer in layers_data:
        results = layer.get("results", {})
        fallback_flags.append(1 if results.get("filtered_stats_fallback_to_raw", False) else 0)
        never_settled_flags.append(1 if results.get("settling_status") == "never_settled" else 0)
        overlap = results.get("time_overlap_fraction")
        low_overlap_flags.append(1 if overlap is not None and overlap < 0.95 else 0)
    flag_rows = {}
    if any(not flag for flag in [False] + fallback_flags):
        flag_rows["Fallback"] = fallback_flags
    if any(not flag for flag in [False] + never_settled_flags):
        flag_rows["Settle"] = never_settled_flags
    if any(not flag for flag in [False] + low_overlap_flags):
        flag_rows["Overlap"] = low_overlap_flags
    if any(pass_flag is False for pass_flag in pass_flags):
        flag_rows["Fail"] = [0 if passed else 1 for passed in pass_flags]
    _draw_layer_heatmap(
        fig,
        axes["heatmap_title"],
        axes["heatmap_group_header"],
        axes["heatmap_metric_header"],
        axes["heatmap_side_header"],
        axes["heatmap"],
        np.array([np.abs(mean_x_all), std_x_all, max_x_all, np.abs(mean_y_all), std_y_all, max_y_all]),
        layer_labels,
        ["Mean", "Std", "Max", "Mean", "Std", "Max"],
        flag_rows=flag_rows if flag_rows else None,
        flag_ax=axes["heatmap_flags"],
        flag_legend_ax=axes["heatmap_flag_legend"],
        cbar_ax=axes["heatmap_cbar"],
    )

    # Bottom panels
    ax_filter = axes["bottom_left"]
    ax_filter.axis("off")
    _draw_analysis_info_panel(ax_filter, layers_data, report_mode, analysis_config)
    ax_worst = axes["bottom_right"]
    ax_worst.axis("off")
    worst_order = np.argsort(worst_axis_error)[::-1][: min(5, num_layers)]
    if len(worst_order) > 0:
        ax_worst.text(0.02, 0.94, "Worst Layers", ha="left", va="top", fontsize=8, fontweight="bold", transform=ax_worst.transAxes)
        ax_worst.text(
            0.02, 0.84,
            "\n".join([f"L{layer_labels[idx]}: max_x {max_x_all[idx]:.2f} mm, max_y {max_y_all[idx]:.2f} mm" for idx in worst_order]),
            ha="left", va="top", fontsize=6.5, family="monospace", transform=ax_worst.transAxes,
        )
    return fig


def _generate_point_gamma_summary_page(
    beam_name,
    beam_data,
    *,
    patient_id="",
    patient_name="",
    analysis_config=None,
):
    from datetime import date as _date

    layers_data = beam_data["layers"]
    num_layers = len(layers_data)
    metrics, all_plan_pos, all_log_pos, _, layer_labels, _, _ = _collect_beam_metrics(
        layers_data, "raw"
    )
    gamma_metrics = _collect_point_gamma_beam_metrics(layers_data)

    mean_x_all = metrics["mean_x"]
    mean_y_all = metrics["mean_y"]
    std_x_all = metrics["std_x"]
    std_y_all = metrics["std_y"]
    rmse_x_all = metrics["rmse_x"]
    rmse_y_all = metrics["rmse_y"]
    max_x_all = metrics["max_x"]
    max_y_all = metrics["max_y"]
    p95_x_all = metrics["p95_x"]
    p95_y_all = metrics["p95_y"]

    similarity_str = "N/A"
    if all_plan_pos and all_log_pos:
        plan_concat = np.vstack(all_plan_pos).ravel()
        log_concat = np.vstack(all_log_pos).ravel()
        if len(plan_concat) == len(log_concat) and len(plan_concat) > 1:
            corr, _ = pearsonr(plan_concat, log_concat)
            similarity_str = f"{corr:.6f}"

    verdict, pass_color = _gamma_beam_verdict(gamma_metrics["beam_pass_rate"])
    global_mean_x = np.mean(mean_x_all) if mean_x_all else 0
    global_mean_y = np.mean(mean_y_all) if mean_y_all else 0
    global_std_x = np.mean(std_x_all) if std_x_all else 0
    global_std_y = np.mean(std_y_all) if std_y_all else 0
    global_rmse_x = np.mean(rmse_x_all) if rmse_x_all else 0
    global_rmse_y = np.mean(rmse_y_all) if rmse_y_all else 0
    global_max_x = max(max_x_all) if max_x_all else 0
    global_max_y = max(max_y_all) if max_y_all else 0
    global_p95_x = np.mean(p95_x_all) if p95_x_all else 0
    global_p95_y = np.mean(p95_y_all) if p95_y_all else 0

    axes = build_summary_skeleton(
        beam_name=beam_name,
        verdict_text=f"{verdict} {gamma_metrics['beam_pass_rate']:.0f}%",
        verdict_color=pass_color,
        subtitle_line=f"Patient ID: {patient_id}    |    Name: {patient_name}    |    Date: {_date.today().isoformat()}    |    Layers: {num_layers}",
        extra_subtitle="Point Gamma Summary",
        extra_subtitle_bold=True,
        has_top_summary=True,
        top_summary_rows=2,
        top_summary_bounds=(0.06, 0.94, 0.785, 0.9),
        top_summary_hspace=0.3,
        middle_width_ratios=(1.0, 1.2),
        middle_bounds=(0.06, 0.97, 0.13, 0.79),
        left_height_ratios=(0.04, 0.01, 0.85, 0.06, 0.04),
        left_hspace=0.03,
        right_height_ratios=(0.06, 0.02, 0.03, 0.825, 0.025, 0.04),
        right_hspace=0.005,
        bottom_width_ratios=None,
        bottom_bounds=(0.06, 0.97, 0.015, 0.09),
    )
    fig = axes["fig"]

    # Top summary tables
    _draw_position_summary_table(
        axes["top_summary_0"],
        global_mean_x=global_mean_x,
        global_mean_y=global_mean_y,
        global_std_x=global_std_x,
        global_std_y=global_std_y,
        global_rmse_x=global_rmse_x,
        global_rmse_y=global_rmse_y,
        global_max_x=global_max_x,
        global_max_y=global_max_y,
        global_p95_x=global_p95_x,
        global_p95_y=global_p95_y,
        similarity_str=similarity_str,
    )
    _draw_gamma_summary_table(
        axes["top_summary_1"],
        num_layers=num_layers,
        beam_pass_rate=gamma_metrics["beam_pass_rate"],
        beam_gamma_mean=gamma_metrics["beam_gamma_mean"],
        beam_gamma_max=gamma_metrics["beam_gamma_max"],
        evaluated_point_total=gamma_metrics["evaluated_point_total"],
        beam_position_error_mean=gamma_metrics["beam_position_error_mean"],
        beam_count_error_mean=gamma_metrics["beam_count_error_mean"],
    )

    # Left panel: layer trend plot
    ax_err = axes["trend"]
    layer_idx = np.arange(1, num_layers + 1)
    y_x = layer_idx - 0.16
    y_y = layer_idx + 0.16
    ax_err.errorbar(mean_x_all, y_x, xerr=std_x_all, fmt="o", markersize=3.5, linewidth=1.0, capsize=2.5, color="#1f77b4", ecolor="#1f77b4", label="X mean \u00b1 std", zorder=3)
    ax_err.errorbar(mean_y_all, y_y, xerr=std_y_all, fmt="s", markersize=3.2, linewidth=1.0, capsize=2.5, color="#ff7f0e", ecolor="#ff7f0e", label="Y mean \u00b1 std", zorder=3)
    ax_err.scatter(mean_x_all, y_x, c=["#2ecc71" if passed else "#e74c3c" for passed in gamma_metrics["pass_flags"]], s=14, zorder=4, edgecolors="white", linewidths=0.3)
    ax_err.scatter(mean_y_all, y_y, c=["#2ecc71" if passed else "#e74c3c" for passed in gamma_metrics["pass_flags"]], s=14, zorder=4, edgecolors="white", linewidths=0.3, marker="s")
    ax_err.axvspan(-THRESHOLDS["mean_diff_mm"], THRESHOLDS["mean_diff_mm"],
                   alpha=0.12, color="#2ecc71", zorder=1, label=f"\u00b1{THRESHOLDS['mean_diff_mm']} mm mean target")
    for x_pos, style, color in (
        (0, "-", "#7f8c8d"),
        (THRESHOLDS["mean_diff_mm"], "--", "#95a5a6"),
        (-THRESHOLDS["mean_diff_mm"], "--", "#95a5a6"),
    ):
        ax_err.axvline(x_pos, linestyle=style, linewidth=0.8 if style != "-" else 0.9, color=color, alpha=0.8)
    ax_err.set_xlabel("Deviation (mm)", fontsize=7)
    ax_err.set_ylabel("Layer", fontsize=7)
    ax_err.set_yticks(layer_idx)
    ax_err.set_yticklabels(layer_labels)
    ax_err.set_ylim(num_layers + 0.6, 0.4)
    ax_err.tick_params(labelsize=6)
    ax_err.grid(True, alpha=0.3, axis="x")
    if num_layers > 25:
        ax_err.tick_params(axis="y", labelsize=4)
    all_devs = np.concatenate([np.array(mean_x_all) - np.array(std_x_all), np.array(mean_x_all) + np.array(std_x_all),
                               np.array(mean_y_all) - np.array(std_y_all), np.array(mean_y_all) + np.array(std_y_all)])
    dev_min = min(float(all_devs.min()), -THRESHOLDS["mean_diff_mm"])
    dev_max = max(float(all_devs.max()), THRESHOLDS["mean_diff_mm"])
    margin = max(0.2, (dev_max - dev_min) * 0.1)
    ax_err.set_xlim(dev_min - margin, dev_max + margin)
    ax_err.legend(fontsize=5, loc="upper left")

    # Right panel: layer heatmap with gamma side column
    _draw_layer_heatmap(
        fig,
        axes["heatmap_title"],
        axes["heatmap_group_header"],
        axes["heatmap_metric_header"],
        axes["heatmap_side_header"],
        axes["heatmap"],
        np.array([np.abs(mean_x_all), std_x_all, max_x_all, np.abs(mean_y_all), std_y_all, max_y_all]),
        layer_labels,
        ["Mean", "Std", "Max", "Mean", "Std", "Max"],
        flag_ax=axes["heatmap_flags"],
        flag_legend_ax=axes["heatmap_flag_legend"],
        cbar_ax=axes["heatmap_cbar"],
        side_values=gamma_metrics["layer_pass_rates"],
        side_label="Gamma",
        side_cmap=plt.cm.RdYlGn,
        side_vmin=0,
        side_vmax=100,
        side_text_labels=[f"{value:.0f}%" for value in gamma_metrics["layer_pass_rates"]],
    )

    # Bottom panel
    ax_filter = axes["bottom"]
    ax_filter.axis("off")
    _draw_point_gamma_analysis_info_panel(
        ax_filter,
        analysis_config,
    )
    return fig
