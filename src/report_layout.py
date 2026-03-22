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
    header_ax,
    ax,
    heatmap_values,
    layer_labels,
    metric_labels,
    flag_rows=None,
    flag_ax=None,
    flag_legend_ax=None,
    cbar_ax=None,
):
    heatmap_values = np.asarray(heatmap_values, dtype=float)
    num_metrics, num_layers = heatmap_values.shape if heatmap_values.size else (0, 0)

    title_ax.axis("off")
    title_ax.text(0.5, 0.5, "Layer Heatmap", ha="center", va="center", fontsize=9, fontweight="bold", transform=title_ax.transAxes)
    header_ax.axis("off")
    if num_metrics >= 6:
        header_ax.set_xlim(-0.5, num_metrics - 0.5)
        header_ax.set_ylim(0, 1)
        for idx, label in enumerate(metric_labels):
            header_ax.text(idx, 0.40, label, ha="center", va="center", fontsize=6)
        header_ax.plot([-0.5, 2.5], [0.57, 0.57], color="#34495e", linewidth=0.8)
        header_ax.plot([2.5, 5.5], [0.57, 0.57], color="#34495e", linewidth=0.8)
        header_ax.text(1.0, 0.61, "X", ha="center", va="bottom", fontsize=6, fontweight="bold")
        header_ax.text(4.0, 0.61, "Y", ha="center", va="bottom", fontsize=6, fontweight="bold")
    if flag_rows:
        header_ax.text(1.055, 0.50, "Flag", ha="center", va="center", fontsize=6, transform=header_ax.transAxes, clip_on=False)

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
    if flag_rows:
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

    fig = plt.figure(figsize=A4_FIGSIZE)
    fig.text(0.50, 0.97, beam_name, ha="center", va="top", fontsize=16, fontweight="bold")
    fig.text(
        0.95, 0.97,
        f"{verdict} {num_pass}/{total_spots} ({pass_rate:.0f}%)",
        ha="right", va="top", fontsize=10, fontweight="bold", color="white",
        bbox=dict(boxstyle="round,pad=0.3", facecolor=pass_color, edgecolor="none"),
    )
    fig.text(
        0.50, 0.935,
        f"Patient ID: {patient_id}    |    Name: {patient_name}    |    Date: {_date.today().isoformat()}    |    Layers: {num_layers}",
        ha="center", va="top", fontsize=8, color="#555555",
    )
    if report_mode != "raw":
        fig.text(0.50, 0.918, f"Zero-dose filter active: {report_mode} metrics shown", ha="center", va="top", fontsize=7, color="#555555")

    radial_means = np.sqrt(np.array(mean_x_all) ** 2 + np.array(mean_y_all) ** 2)
    radial_per_layer = np.sqrt(np.array(rmse_x_all) ** 2 + np.array(rmse_y_all) ** 2)
    global_radial_mean = float(np.mean(radial_means)) if len(radial_means) else 0
    global_radial_max = float(np.max(radial_means)) if len(radial_means) else 0
    global_radial_p95 = float(np.percentile(radial_per_layer, 95)) if len(radial_per_layer) else 0
    global_radial_rmse = float(np.mean(radial_per_layer)) if len(radial_per_layer) else 0

    thr_mean = THRESHOLDS["mean_diff_mm"]
    thr_std = THRESHOLDS["std_diff_mm"]
    thr_max = THRESHOLDS["max_abs_diff_mm"]
    ax_metrics = fig.add_axes([0.06, 0.79, 0.88, 0.10])
    ax_metrics.axis("off")
    col_labels = ["", f"Mean (\u2264{thr_mean})", f"Std (\u2264{thr_std})", "RMSE (mm)", f"Max (\u2264{thr_max})", "P95 (mm)", "Similarity"]
    metrics_table = ax_metrics.table(
        cellText=[
            ["X", f"{global_mean_x:+.3f}", f"{global_std_x:.3f}", f"{global_rmse_x:.3f}", f"{global_max_x:.3f}", f"{global_p95_x:.3f}", similarity_str],
            ["Y", f"{global_mean_y:+.3f}", f"{global_std_y:.3f}", f"{global_rmse_y:.3f}", f"{global_max_y:.3f}", f"{global_p95_y:.3f}", ""],
            ["Radial", f"{global_radial_mean:.3f}", "", f"{global_radial_rmse:.3f}", f"{global_radial_max:.3f}", f"{global_radial_p95:.3f}", ""],
        ],
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
        colWidths=[0.12, 0.15, 0.15, 0.14, 0.14, 0.14, 0.16],
    )
    metrics_table.auto_set_font_size(False)
    metrics_table.set_fontsize(6.5)
    metrics_table.scale(1.0, 1.18)
    for idx in range(len(col_labels)):
        metrics_table[0, idx].set_facecolor("#34495e")
        metrics_table[0, idx].set_text_props(color="white", fontweight="bold", va="center")
    for row_idx, color in ((1, "#3498db"), (2, "#e67e22"), (3, "#8e44ad")):
        metrics_table[row_idx, 0].set_facecolor(color)
        metrics_table[row_idx, 0].set_text_props(color="white", fontweight="bold", va="center")
    for (_, _), cell in metrics_table.get_celld().items():
        cell.set_text_props(va="center")
        cell.PAD = 0.02

    for row_idx, row_vals in enumerate([
        (abs(global_mean_x), global_std_x, global_rmse_x, global_max_x, global_p95_x),
        (abs(global_mean_y), global_std_y, global_rmse_y, global_max_y, global_p95_y),
        (global_radial_mean, 0, global_radial_rmse, global_radial_max, global_radial_p95),
    ], start=1):
        for col_idx, threshold in {1: thr_mean, 2: thr_std, 4: thr_max}.items():
            ratio = row_vals[col_idx - 1] / threshold if threshold > 0 else 0
            metrics_table[row_idx, col_idx].set_facecolor(
                "#d5f5e3" if ratio <= 0.5 else "#fdebd0" if ratio <= 1.0 else "#fadbd8"
            )

    middle_gs = fig.add_gridspec(1, 2, left=0.06, right=0.97, bottom=0.28, top=0.78, wspace=0.16, width_ratios=[0.9, 1.3])
    left_gs = middle_gs[0, 0].subgridspec(5, 1, height_ratios=[0.06, 0.08, 0.76, 0.06, 0.04], hspace=0.08)
    ax_trend_title = fig.add_subplot(left_gs[0, 0])
    ax_trend_title.axis("off")
    ax_trend_title.text(0.5, 0.5, "Layer Trend", ha="center", va="center", fontsize=9, fontweight="bold", transform=ax_trend_title.transAxes)
    ax_err = fig.add_subplot(left_gs[1:, 0])
    layer_idx = np.arange(1, num_layers + 1)
    worst_axis_error = np.maximum(np.array(max_x_all), np.array(max_y_all))
    y_x = layer_idx - 0.16
    y_y = layer_idx + 0.16
    ax_err.errorbar(mean_x_all, y_x, xerr=std_x_all, fmt="o", markersize=3.5, linewidth=1.0, capsize=2.5, color="#1f77b4", ecolor="#1f77b4", label="X mean ± std", zorder=3)
    ax_err.errorbar(mean_y_all, y_y, xerr=std_y_all, fmt="s", markersize=3.2, linewidth=1.0, capsize=2.5, color="#ff7f0e", ecolor="#ff7f0e", label="Y mean ± std", zorder=3)
    ax_err.scatter(mean_x_all, y_x, c=["#2ecc71" if passed else "#e74c3c" for passed in pass_flags], s=14, zorder=4, edgecolors="white", linewidths=0.3)
    ax_err.scatter(mean_y_all, y_y, c=["#2ecc71" if passed else "#e74c3c" for passed in pass_flags], s=14, zorder=4, edgecolors="white", linewidths=0.3, marker="s")
    for x_pos, style, color, label in (
        (0, "-", "#7f8c8d", None),
        (THRESHOLDS["mean_diff_mm"], "--", "#95a5a6", None),
        (-THRESHOLDS["mean_diff_mm"], "--", "#95a5a6", f"±{THRESHOLDS['mean_diff_mm']} mm mean target"),
        (THRESHOLDS["max_abs_diff_mm"], ":", "#bdc3c7", None),
        (-THRESHOLDS["max_abs_diff_mm"], ":", "#bdc3c7", f"±{THRESHOLDS['max_abs_diff_mm']} mm max limit"),
    ):
        ax_err.axvline(x_pos, linestyle=style, linewidth=0.8 if style != "-" else 0.9, color=color, alpha=0.9 if style != "--" else 0.8, label=label)
    ax_err.set_xlabel("Deviation (mm)", fontsize=7)
    ax_err.set_ylabel("Layer", fontsize=7)
    ax_err.set_yticks(layer_idx)
    ax_err.set_yticklabels(layer_labels)
    ax_err.set_ylim(num_layers + 0.6, 0.4)
    ax_err.tick_params(labelsize=6)
    ax_err.grid(True, alpha=0.3, axis="x")
    if num_layers > 25:
        ax_err.tick_params(axis="y", labelsize=4)
    ax_err.legend(fontsize=5, loc="upper left")

    right_gs = middle_gs[0, 1].subgridspec(5, 2, height_ratios=[0.06, 0.06, 0.815, 0.025, 0.04], width_ratios=[0.90, 0.10], hspace=0.01, wspace=0.08)
    ax_heatmap_title = fig.add_subplot(right_gs[0, :])
    ax_heatmap_header = fig.add_subplot(right_gs[1, 0])
    ax_heatmap = fig.add_subplot(right_gs[2, 0])
    ax_heatmap_flags = fig.add_subplot(right_gs[2, 1])
    ax_heatmap_cbar = fig.add_subplot(right_gs[3, :])
    ax_heatmap_flag_legend = fig.add_subplot(right_gs[4, :])
    heatmap_pos = ax_heatmap.get_position()
    header_pos = ax_heatmap_header.get_position()
    tightened_heatmap_top = header_pos.y0 - 0.0002
    if tightened_heatmap_top > heatmap_pos.y1:
        ax_heatmap.set_position([heatmap_pos.x0, heatmap_pos.y0, heatmap_pos.width, tightened_heatmap_top - heatmap_pos.y0])
        flag_pos = ax_heatmap_flags.get_position()
        ax_heatmap_flags.set_position([flag_pos.x0, flag_pos.y0, flag_pos.width, tightened_heatmap_top - flag_pos.y0])
    for axis in (ax_heatmap_cbar, ax_heatmap_flag_legend):
        pos = axis.get_position()
        axis.set_position([pos.x0, pos.y0 - 0.006, pos.width, pos.height])
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
        ax_heatmap_title,
        ax_heatmap_header,
        ax_heatmap,
        np.array([np.abs(mean_x_all), std_x_all, max_x_all, np.abs(mean_y_all), std_y_all, max_y_all]),
        layer_labels,
        ["Mean", "Std", "Max", "Mean", "Std", "Max"],
        flag_rows=flag_rows if flag_rows else None,
        flag_ax=ax_heatmap_flags,
        flag_legend_ax=ax_heatmap_flag_legend,
        cbar_ax=ax_heatmap_cbar,
    )

    bottom_gs = fig.add_gridspec(1, 2, left=0.06, right=0.97, bottom=0.03, top=0.24, wspace=0.10, width_ratios=[1.4, 1.0])
    ax_filter = fig.add_subplot(bottom_gs[0, 0])
    ax_filter.axis("off")
    _draw_analysis_info_panel(ax_filter, layers_data, report_mode, analysis_config)
    ax_worst = fig.add_subplot(bottom_gs[0, 1])
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


def _generate_executive_summary(report_data, patient_id, patient_name, report_mode):
    from datetime import date as _date

    fig = plt.figure(figsize=A4_FIGSIZE)
    fig.text(0.50, 0.97, "Executive Summary", ha="center", va="top", fontsize=18, fontweight="bold")
    fig.text(0.50, 0.935, f"Patient ID: {patient_id}    |    Name: {patient_name}    |    Date: {_date.today().isoformat()}", ha="center", va="top", fontsize=9, color="#555555")

    beam_rows = []
    fraction_passed = 0
    fraction_total = 0
    for beam_name, beam_data in report_data.items():
        if beam_name.startswith("_"):
            continue
        layers_data = beam_data.get("layers", [])
        if not layers_data:
            continue
        passed_spots = 0
        total_spots = 0
        mean_x_vals = []
        mean_y_vals = []
        max_err_vals = []
        for layer in layers_data:
            results = layer.get("results", {})
            mean_x_vals.append(_metric_value(results, "mean_diff_x", report_mode))
            mean_y_vals.append(_metric_value(results, "mean_diff_y", report_mode))
            max_err_vals.append(max(_metric_value(results, "max_abs_diff_x", report_mode), _metric_value(results, "max_abs_diff_y", report_mode)))
            lp, lt = _spot_pass_summary(results, report_mode=report_mode)
            passed_spots += lp
            total_spots += lt
        pass_rate = passed_spots / total_spots * 100 if total_spots > 0 else 0
        verdict, color = _beam_verdict(pass_rate)
        beam_rows.append({
            "name": beam_name,
            "layers": len(layers_data),
            "pass_rate": pass_rate,
            "passed": passed_spots,
            "total": total_spots,
            "mean_x": np.mean(mean_x_vals) if mean_x_vals else 0,
            "mean_y": np.mean(mean_y_vals) if mean_y_vals else 0,
            "max_err": max(max_err_vals) if max_err_vals else 0,
            "verdict": verdict,
            "color": color,
        })
        fraction_passed += passed_spots
        fraction_total += total_spots

    fraction_rate = fraction_passed / fraction_total * 100 if fraction_total > 0 else 0
    fraction_verdict, fraction_color = _beam_verdict(fraction_rate)
    fig.text(
        0.50, 0.905,
        f"{fraction_verdict}  ({fraction_passed}/{fraction_total} spots, {fraction_rate:.0f}%)",
        ha="center", va="top", fontsize=13, fontweight="bold", color="white",
        bbox=dict(boxstyle="round,pad=0.4", facecolor=fraction_color, edgecolor="none"),
    )

    ax_tbl = fig.add_axes([0.06, 0.40, 0.88, 0.48])
    ax_tbl.axis("off")
    col_labels = ["Beam", "Layers", "Pass Rate", "Mean X (mm)", "Mean Y (mm)", "Max |err| (mm)", "Verdict"]
    table_rows = [[
        beam["name"],
        str(beam["layers"]),
        f"{beam['passed']}/{beam['total']} ({beam['pass_rate']:.0f}%)",
        f"{beam['mean_x']:+.3f}",
        f"{beam['mean_y']:+.3f}",
        f"{beam['max_err']:.3f}",
        beam["verdict"],
    ] for beam in beam_rows]
    if not table_rows:
        ax_tbl.text(0.5, 0.5, "No beam data available", ha="center", va="center", fontsize=12)
        return fig

    table = ax_tbl.table(cellText=table_rows, colLabels=col_labels, loc="upper center", cellLoc="center")
    table.auto_set_font_size(False)
    num_beams = len(table_rows)
    table.set_fontsize(9 if num_beams <= 6 else (7 if num_beams <= 12 else 6))
    table.scale(1.0, min(2.5, max(1.2, 14.0 / (num_beams + 1))))
    for idx in range(len(col_labels)):
        table[0, idx].set_facecolor("#34495e")
        table[0, idx].set_text_props(color="white", fontweight="bold")
    for row_idx, beam in enumerate(beam_rows, start=1):
        table[row_idx, 6].set_facecolor(beam["color"])
        table[row_idx, 6].set_text_props(color="white", fontweight="bold")
        table[row_idx, 2].set_facecolor("#d5f5e3" if beam["pass_rate"] == 100 else "#fdebd0" if beam["pass_rate"] >= 80 else "#fadbd8")

    fig.text(0.50, 0.37, f"Report mode: {report_mode}    |    Thresholds: Mean \u2264{THRESHOLDS['mean_diff_mm']} mm, Std \u2264{THRESHOLDS['std_diff_mm']} mm, Max \u2264{THRESHOLDS['max_abs_diff_mm']} mm", ha="center", va="top", fontsize=7, color="#888888")
    return fig
