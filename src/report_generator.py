import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import Normalize
import numpy as np
from scipy.stats import pearsonr
import os
import logging

logger = logging.getLogger(__name__)

# Figure size constants
A4_FIGSIZE = (8.27, 11.69)  # A4 paper size in inches
POSITION_PLOT_FIGSIZE = (8, 8)

# Pass/fail thresholds for summary report (mm)
THRESHOLDS = {
    "mean_diff_mm": 1.0,
    "std_diff_mm": 1.5,
    "max_abs_diff_mm": 3.0,
}


def _metric_key(results, base_key, report_mode):
    if report_mode != "raw":
        filtered_key = f"filtered_{base_key}"
        if filtered_key in results:
            return filtered_key
    return base_key


def _metric_value(results, base_key, report_mode):
    return results.get(_metric_key(results, base_key, report_mode), 0)


def _generate_error_bar_plot_for_beam(beam_name, layers_data, report_mode="raw"):
    """Generates an error bar plot figure for a single beam."""
    num_layers = len(layers_data)
    layer_indices = np.arange(1, num_layers + 1)
    mean_diff_x = [
        _metric_value(layer.get("results", {}), "mean_diff_x", report_mode)
        for layer in layers_data
    ]
    mean_diff_y = [
        _metric_value(layer.get("results", {}), "mean_diff_y", report_mode)
        for layer in layers_data
    ]
    std_diff_x = [
        _metric_value(layer.get("results", {}), "std_diff_x", report_mode)
        for layer in layers_data
    ]
    std_diff_y = [
        _metric_value(layer.get("results", {}), "std_diff_y", report_mode)
        for layer in layers_data
    ]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=A4_FIGSIZE)
    fig.suptitle(f"Position Difference (plan - log) - {beam_name}", fontsize=16)

    # X-position difference plot
    ax1.errorbar(layer_indices, mean_diff_x, yerr=std_diff_x, fmt="o-", capsize=5)
    ax1.set_title("X Position Difference")
    ax1.set_xlabel("Layer Number")
    ax1.set_ylabel("Difference (mm)")
    ax1.grid(True)

    # Y-position difference plot
    ax2.errorbar(
        layer_indices, mean_diff_y, yerr=std_diff_y, fmt="o-", capsize=5, color="orange"
    )
    ax2.set_title("Y Position Difference")
    ax2.set_xlabel("Layer Number")
    ax2.set_ylabel("Difference (mm)")
    ax2.grid(True)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return fig


def _generate_per_layer_position_plot(
    plan_positions,
    log_positions,
    layer_index,
    beam_name,
    global_min_coords,
    global_max_coords,
):
    """Generates a 2D position comparison plot figure for a single layer with outlier rejection."""

    # Filter log positions
    filtered_log_positions = log_positions[
        (log_positions[:, 0] >= global_min_coords[0])
        & (log_positions[:, 0] <= global_max_coords[0])
        & (log_positions[:, 1] >= global_min_coords[1])
        & (log_positions[:, 1] <= global_max_coords[1])
    ]

    fig, ax = plt.subplots(figsize=POSITION_PLOT_FIGSIZE)

    ax.plot(plan_positions[:, 0], plan_positions[:, 1], "r-", linewidth=1, label="Plan")

    if filtered_log_positions.size > 0:
        sampled_log = (
            filtered_log_positions[::10]
            if len(filtered_log_positions) > 10
            else filtered_log_positions
        )
        ax.scatter(
            sampled_log[:, 0], sampled_log[:, 1], c="b", marker="+", s=10, label="Log"
        )
    else:
        logger.warning(
            f"No log data within the margin for layer {layer_index} of {beam_name}."
        )

    ax.set_xlabel("X Position (mm)")
    ax.set_ylabel("Y Position (mm)")
    ax.set_title(f"2D Position - Layer {layer_index // 2 + 1}")
    ax.legend()
    ax.grid(True)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(global_min_coords[0], global_max_coords[0])
    ax.set_ylim(global_min_coords[1], global_max_coords[1])

    return fig


def _save_plots_to_pdf_grid(pdf, plots, beam_name):
    """Saves up to 6 plots to a single PDF page in a 3x2 grid."""
    fig = plt.figure(figsize=A4_FIGSIZE)
    fig.suptitle(f"2D Position Comparison - {beam_name}", fontsize=16)

    for i, plot_fig in enumerate(plots):
        if i >= 6:
            break

        # This is a workaround to copy the content of the existing plot figure to a subplot
        ax_src = plot_fig.axes[0]
        ax_dest = fig.add_subplot(3, 2, i + 1)

        for line in ax_src.get_lines():
            ax_dest.plot(
                line.get_xdata(),
                line.get_ydata(),
                color=line.get_color(),
                linestyle=line.get_linestyle(),
                linewidth=line.get_linewidth(),
                label=line.get_label(),
            )

        for collection in ax_src.collections:
            ax_dest.scatter(
                collection.get_offsets()[:, 0],
                collection.get_offsets()[:, 1],
                c=collection.get_facecolors(),
                marker=collection.get_paths()[0],
                s=collection.get_sizes(),
                label=collection.get_label(),
            )

        ax_dest.set_title(ax_src.get_title())
        ax_dest.set_xlabel(ax_src.get_xlabel())
        ax_dest.set_ylabel(ax_src.get_ylabel())
        ax_dest.grid(True)
        ax_dest.legend()
        ax_dest.set_aspect("equal", adjustable="box")
        ax_dest.set_xlim(ax_src.get_xlim())
        ax_dest.set_ylim(ax_src.get_ylim())

        plt.close(plot_fig)  # Close the original figure to save memory

    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    pdf.savefig(fig)
    plt.close(fig)


def _layer_passes(results, report_mode="raw"):
    """Check whether a single layer's results are within thresholds."""
    mean_ok = (
        abs(_metric_value(results, "mean_diff_x", report_mode))
        <= THRESHOLDS["mean_diff_mm"]
        and abs(_metric_value(results, "mean_diff_y", report_mode))
        <= THRESHOLDS["mean_diff_mm"]
    )
    std_ok = (
        _metric_value(results, "std_diff_x", report_mode)
        <= THRESHOLDS["std_diff_mm"]
        and _metric_value(results, "std_diff_y", report_mode)
        <= THRESHOLDS["std_diff_mm"]
    )
    max_ok = (
        _metric_value(results, "max_abs_diff_x", report_mode)
        <= THRESHOLDS["max_abs_diff_mm"]
        and _metric_value(results, "max_abs_diff_y", report_mode)
        <= THRESHOLDS["max_abs_diff_mm"]
    )
    return mean_ok and std_ok and max_ok


def _beam_verdict(pass_rate):
    """Derive beam-level verdict from spot pass rate."""
    if pass_rate == 100:
        return "PASS", "#2ecc71"
    elif pass_rate >= 80:
        return "CONDITIONAL", "#e67e22"
    else:
        return "FAIL", "#e74c3c"


def _draw_filter_panel(ax, layers_data, report_mode):
    """Draw a filter transparency panel showing the sample funnel and operational metadata."""
    total_samples = 0
    settled_samples = 0
    included_samples = 0
    filtered_out_samples = 0
    mu_fraction_sum = 0.0
    mu_fraction_count = 0
    fallback_layers = []
    never_settled_layers = []
    overlap_values = []

    for layer in layers_data:
        r = layer.get("results", {})
        raw_idx = layer.get("layer_index", 0)
        layer_label = str(int(raw_idx) // 2 + 1)

        # Count total samples from diff arrays
        diff_x = r.get("diff_x")
        if diff_x is not None:
            n = len(np.asarray(diff_x))
            total_samples += n
        else:
            continue

        settling_count = r.get("settling_samples_count", 0)
        settled_samples += (n - settling_count)

        # Track settling issues
        if r.get("settling_status") == "never_settled":
            never_settled_layers.append(layer_label)

        # Track time overlap
        overlap = r.get("time_overlap_fraction")
        if overlap is not None:
            overlap_values.append(overlap)

        if report_mode != "raw":
            num_included = r.get("num_included_samples", 0)
            num_filtered = r.get("num_filtered_samples", 0)
            included_samples += num_included
            filtered_out_samples += num_filtered
            mu_frac = r.get("filtered_mu_fraction_estimate")
            if mu_frac is not None:
                mu_fraction_sum += mu_frac
                mu_fraction_count += 1
            if r.get("filtered_stats_fallback_to_raw", False):
                fallback_layers.append(layer_label)
        else:
            included_samples += (n - settling_count)

    ax.set_title("Filter Transparency", fontsize=8, fontweight="bold", pad=4)

    warn_color = "#c0392b"

    # Build table rows
    if report_mode == "raw":
        table_data = [
            ["Total samples", f"{total_samples:,}"],
            ["After settling", f"{settled_samples:,}"],
            ["Filter mode", "raw (off)"],
        ]
    else:
        avg_mu_pct = (
            (mu_fraction_sum / mu_fraction_count * 100)
            if mu_fraction_count > 0
            else 0
        )
        table_data = [
            ["Total", f"{total_samples:,}"],
            ["Settled", f"{settled_samples:,}"],
            ["Filtered out", f"{filtered_out_samples:,}"],
            ["Included", f"{included_samples:,}"],
            ["MU filtered-out", f"{avg_mu_pct:.1f}%"],
        ]

    if overlap_values:
        min_overlap = min(overlap_values)
        table_data.append(["Time overlap (min)", f"{min_overlap:.1%}"])

    if never_settled_layers:
        trunc = never_settled_layers[:5]
        label = f"L{', L'.join(trunc)}"
        if len(never_settled_layers) > 5:
            label += f" +{len(never_settled_layers) - 5}"
        table_data.append(["Never settled", label])

    if fallback_layers:
        table_data.append(["Fallback to raw", f"L{', L'.join(fallback_layers)}"])

    tbl = ax.table(
        cellText=table_data,
        colLabels=["Metric", "Value"],
        loc="upper center", cellLoc="left",
        colWidths=[0.55, 0.45],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(6.5)
    num_rows = len(table_data)
    row_scale = min(1.6, max(0.9, 10.0 / (num_rows + 1)))
    tbl.scale(1.0, row_scale)

    # Style header
    for j in range(2):
        tbl[0, j].set_facecolor("#34495e")
        tbl[0, j].set_text_props(color="white", fontweight="bold", fontsize=6.5)

    # Style data rows
    for i in range(num_rows):
        row_idx = i + 1
        label_text = table_data[i][0]
        tbl[row_idx, 0].set_text_props(fontweight="bold")
        tbl[row_idx, 0].set_facecolor("#f8f8f8")
        tbl[row_idx, 1].set_facecolor("white")

        # Highlight warnings in red
        is_warning = False
        if label_text == "Time overlap (min)" and overlap_values and min(overlap_values) < 0.95:
            is_warning = True
        elif label_text in ("Never settled", "Fallback to raw"):
            is_warning = True

        if is_warning:
            tbl[row_idx, 0].set_text_props(fontweight="bold", color=warn_color)
            tbl[row_idx, 1].set_text_props(color=warn_color)
            tbl[row_idx, 1].set_facecolor("#fdedec")


def _spot_pass_summary(results, report_mode="raw"):
    """Count passed spots using the current thresholds on per-spot sample stats."""
    diff_x_key = _metric_key(results, "diff_x", report_mode)
    diff_y_key = _metric_key(results, "diff_y", report_mode)
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
        if _layer_passes(spot_results, report_mode="raw"):
            passed_spots += 1

    return passed_spots, total_spots


def _draw_layer_table(fig, ax, rows, values, flags, col_labels, colored_cols, cmap, norm):
    """Draw a colored layer metrics table on the given axes."""
    num_rows = len(rows)
    if num_rows == 0:
        return

    table = ax.table(
        cellText=rows, colLabels=col_labels,
        loc="upper center", cellLoc="center",
    )
    table.auto_set_font_size(False)
    if num_rows <= 25:
        tbl_fontsize = 6
    elif num_rows <= 40:
        tbl_fontsize = 5
    else:
        tbl_fontsize = 4
    table.set_fontsize(tbl_fontsize)
    row_scale = min(1.8, max(0.6, 28.0 / (num_rows + 1)))
    table.scale(1.0, row_scale)

    # Style header row
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#34495e")
        table[0, j].set_text_props(color="white", fontweight="bold")

    # Color data cells
    for i in range(num_rows):
        row_idx = i + 1
        vals = values[i]
        passed = flags[i]
        table[row_idx, 0].set_facecolor("#d5f5e3" if passed else "#fadbd8")
        table[row_idx, 0].set_text_props(fontweight="bold")
        for j in range(1, len(col_labels)):
            if j in colored_cols:
                rgba = cmap(norm(vals[j]))
                table[row_idx, j].set_facecolor(rgba)
                luminance = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
                text_color = "white" if luminance < 0.5 else "black"
                table[row_idx, j].set_text_props(color=text_color)

    # Colorbar legend beneath table
    renderer = fig.canvas.get_renderer()
    tbl_window_bbox = table.get_window_extent(renderer)
    tbl_fig_bbox = tbl_window_bbox.transformed(fig.transFigure.inverted())
    cbar_bottom = max(tbl_fig_bbox.y0 - 0.018, 0.01)
    cbar_ax = fig.add_axes([
        tbl_fig_bbox.x0 + 0.02, cbar_bottom,
        tbl_fig_bbox.width - 0.04, 0.012,
    ])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal")
    cbar.ax.tick_params(labelsize=5)
    cbar.set_label("Colormap: |mean|, std  (0 \u2013 3 mm)", fontsize=6)


def _draw_layer_heatmap(
    fig,
    ax,
    heatmap_values,
    layer_labels,
    metric_labels,
    flag_rows=None,
    flag_ax=None,
    cbar_ax=None,
):
    """Draw a compact all-layer heatmap with optional binary flag rows."""
    heatmap_values = np.asarray(heatmap_values, dtype=float)
    num_metrics, num_layers = heatmap_values.shape if heatmap_values.size else (0, 0)

    cmap = plt.cm.RdYlGn_r
    norm = Normalize(vmin=0, vmax=THRESHOLDS["max_abs_diff_mm"])
    image = ax.imshow(
        heatmap_values,
        aspect="auto",
        interpolation="nearest",
        cmap=cmap,
        norm=norm,
        origin="upper",
    )
    ax.set_title("Layer Heatmap", fontsize=9, fontweight="bold", pad=6)
    ax.set_yticks(np.arange(num_metrics))
    ax.set_yticklabels(metric_labels, fontsize=6)
    ax.set_xticks(np.arange(num_layers))

    tick_positions = np.arange(num_layers)
    if num_layers > 25:
        tick_step = max(1, int(np.ceil(num_layers / 25)))
        tick_positions = np.arange(0, num_layers, tick_step)
        ax.set_xticks(tick_positions)
        ax.set_xticklabels([layer_labels[i] for i in tick_positions], fontsize=5)
    else:
        ax.set_xticklabels(layer_labels, fontsize=6)

    ax.set_xlabel("Layer", fontsize=7)
    ax.tick_params(axis="x", rotation=90, pad=1)

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
        row_names = list(flag_rows.keys())
        flag_values = np.asarray([flag_rows[name] for name in row_names], dtype=float)
        if flag_ax is None:
            flag_ax = ax.inset_axes([0.0, -0.30, 1.0, 0.16])
        flag_image = flag_ax.imshow(
            flag_values,
            aspect="auto",
            interpolation="nearest",
            cmap=plt.cm.Reds,
            vmin=0,
            vmax=1,
            origin="upper",
        )
        flag_ax.set_yticks(np.arange(len(row_names)))
        flag_ax.set_yticklabels(row_names, fontsize=5)
        flag_ax.set_xticks(tick_positions)
        flag_ax.set_xticklabels([])
        flag_ax.tick_params(axis="x", length=0, pad=0)
        flag_ax.set_xlabel("Flags", fontsize=6, labelpad=1)

    return image, flag_image


def _generate_summary_page(
    beam_name,
    beam_data,
    patient_id="",
    patient_name="",
    report_mode="raw",
):
    """
    Generates a one-page A4 summary dashboard for a single beam.

    Layout:
        Title bar (top): large beam name + verdict badge (PASS/CONDITIONAL/FAIL)
        Info row: Patient ID, Patient Name, Date, Layer count
        Summary metrics row: compact beam-level statistics
        Middle split:
            Left: vertically long trend plot across layers
            Right: all-layer heatmap
        Bottom: warnings and compact worst-layer summary
    """
    from datetime import date as _date

    layers_data = beam_data["layers"]
    num_layers = len(layers_data)

    # --- Collect per-layer metrics ---
    mean_x_all, mean_y_all = [], []
    std_x_all, std_y_all = [], []
    rmse_x_all, rmse_y_all = [], []
    max_x_all, max_y_all = [], []
    p95_x_all, p95_y_all = [], []
    all_plan_pos, all_log_pos = [], []
    pass_flags = []
    layer_labels = []
    passed_spots = 0
    total_spots = 0

    for layer in layers_data:
        r = layer.get("results", {})
        raw_idx = layer.get("layer_index", 0)
        layer_labels.append(str(int(raw_idx) // 2 + 1))

        mean_x_all.append(_metric_value(r, "mean_diff_x", report_mode))
        mean_y_all.append(_metric_value(r, "mean_diff_y", report_mode))
        std_x_all.append(_metric_value(r, "std_diff_x", report_mode))
        std_y_all.append(_metric_value(r, "std_diff_y", report_mode))
        rmse_x_all.append(_metric_value(r, "rmse_x", report_mode))
        rmse_y_all.append(_metric_value(r, "rmse_y", report_mode))
        max_x_all.append(_metric_value(r, "max_abs_diff_x", report_mode))
        max_y_all.append(_metric_value(r, "max_abs_diff_y", report_mode))
        p95_x_all.append(_metric_value(r, "p95_abs_diff_x", report_mode))
        p95_y_all.append(_metric_value(r, "p95_abs_diff_y", report_mode))

        plan_pos = r.get("plan_positions")
        log_pos = r.get("log_positions")
        if plan_pos is not None:
            all_plan_pos.append(plan_pos)
        if log_pos is not None:
            all_log_pos.append(log_pos)

        pass_flags.append(_layer_passes(r, report_mode=report_mode))
        layer_passed_spots, layer_total_spots = _spot_pass_summary(
            r, report_mode=report_mode
        )
        passed_spots += layer_passed_spots
        total_spots += layer_total_spots

    num_pass = passed_spots
    pass_rate = num_pass / total_spots * 100 if total_spots > 0 else 0

    # Global aggregate metrics
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

    # Similarity index: Pearson correlation of concatenated plan vs log positions
    similarity_str = "N/A"
    if all_plan_pos and all_log_pos:
        plan_concat = np.vstack(all_plan_pos).ravel()
        log_concat = np.vstack(all_log_pos).ravel()
        if len(plan_concat) == len(log_concat) and len(plan_concat) > 1:
            corr, _ = pearsonr(plan_concat, log_concat)
            similarity_str = f"{corr:.6f}"

    # Derive verdict from pass rate
    if pass_rate == 100:
        verdict = "PASS"
        pass_color = "#2ecc71"
    elif pass_rate >= 80:
        verdict = "CONDITIONAL"
        pass_color = "#e67e22"
    else:
        verdict = "FAIL"
        pass_color = "#e74c3c"

    # --- Build the figure ---
    fig = plt.figure(figsize=A4_FIGSIZE)

    # Layout: title (top 4%), info row (3%), metrics table (12%), plots (remaining)
    # -- Title bar --
    fig.text(
        0.50, 0.97, beam_name,
        ha="center", va="top", fontsize=16, fontweight="bold",
    )
    # Verdict badge with actual pass/fail status
    badge_text = f"{verdict} {num_pass}/{total_spots} ({pass_rate:.0f}%)"
    fig.text(
        0.95, 0.97, badge_text,
        ha="right", va="top", fontsize=10, fontweight="bold", color="white",
        bbox=dict(boxstyle="round,pad=0.3", facecolor=pass_color, edgecolor="none"),
    )

    # -- Patient info row --
    info_text = (
        f"Patient ID: {patient_id}    |    "
        f"Name: {patient_name}    |    "
        f"Date: {_date.today().isoformat()}    |    "
        f"Layers: {num_layers}"
    )
    fig.text(
        0.50, 0.935, info_text,
        ha="center", va="top", fontsize=8, color="#555555",
    )
    if report_mode != "raw":
        fig.text(
            0.50, 0.918,
            f"Zero-dose filter active: {report_mode} metrics shown",
            ha="center", va="top", fontsize=7, color="#555555",
        )

    # -- Radial error (2D) metrics --
    radial_means = np.sqrt(np.array(mean_x_all) ** 2 + np.array(mean_y_all) ** 2)
    global_radial_mean = float(np.mean(radial_means)) if len(radial_means) else 0
    global_radial_max = float(np.max(radial_means)) if len(radial_means) else 0
    # P95 radial from per-layer RMSE values as proxy for radial magnitude
    radial_per_layer = np.sqrt(np.array(rmse_x_all) ** 2 + np.array(rmse_y_all) ** 2)
    global_radial_p95 = float(np.percentile(radial_per_layer, 95)) if len(radial_per_layer) else 0
    global_radial_rmse = float(np.mean(radial_per_layer)) if len(radial_per_layer) else 0

    # -- Metrics table panel --
    thr_mean = THRESHOLDS["mean_diff_mm"]
    thr_std = THRESHOLDS["std_diff_mm"]
    thr_max = THRESHOLDS["max_abs_diff_mm"]
    ax_metrics = fig.add_axes([0.06, 0.79, 0.88, 0.10])
    ax_metrics.axis("off")
    col_labels = [
        "",
        f"Mean (\u2264{thr_mean})",
        f"Std (\u2264{thr_std})",
        "RMSE (mm)",
        f"Max (\u2264{thr_max})",
        "P95 (mm)",
        "Similarity",
    ]
    row_x = ["X", f"{global_mean_x:+.3f}", f"{global_std_x:.3f}", f"{global_rmse_x:.3f}",
             f"{global_max_x:.3f}", f"{global_p95_x:.3f}", similarity_str]
    row_y = ["Y", f"{global_mean_y:+.3f}", f"{global_std_y:.3f}", f"{global_rmse_y:.3f}",
             f"{global_max_y:.3f}", f"{global_p95_y:.3f}", ""]
    row_r = ["Radial", f"{global_radial_mean:.3f}", "", f"{global_radial_rmse:.3f}",
             f"{global_radial_max:.3f}", f"{global_radial_p95:.3f}", ""]
    metrics_table = ax_metrics.table(
        cellText=[row_x, row_y, row_r], colLabels=col_labels,
        loc="center", cellLoc="center",
        colWidths=[0.12, 0.15, 0.15, 0.14, 0.14, 0.14, 0.16],
    )
    metrics_table.auto_set_font_size(False)
    metrics_table.set_fontsize(6.5)
    metrics_table.scale(1.0, 1.18)
    # Style header row
    for j in range(len(col_labels)):
        metrics_table[0, j].set_facecolor("#34495e")
        metrics_table[0, j].set_text_props(color="white", fontweight="bold", va="center")
    # Style axis label cells
    metrics_table[1, 0].set_facecolor("#3498db")
    metrics_table[1, 0].set_text_props(color="white", fontweight="bold", va="center")
    metrics_table[2, 0].set_facecolor("#e67e22")
    metrics_table[2, 0].set_text_props(color="white", fontweight="bold", va="center")
    metrics_table[3, 0].set_facecolor("#8e44ad")
    metrics_table[3, 0].set_text_props(color="white", fontweight="bold", va="center")
    for (_, _), cell in metrics_table.get_celld().items():
        cell.set_text_props(va="center")
        cell.PAD = 0.02

    # Color-code metric cells by threshold proximity (green/yellow/red)
    _threshold_checks = {
        1: ("mean", thr_mean),   # Mean column
        2: ("std", thr_std),     # Std column
        4: ("max", thr_max),     # Max column
    }
    for row_i, row_vals in enumerate([
        (abs(global_mean_x), global_std_x, global_rmse_x, global_max_x, global_p95_x),
        (abs(global_mean_y), global_std_y, global_rmse_y, global_max_y, global_p95_y),
        (global_radial_mean, 0, global_radial_rmse, global_radial_max, global_radial_p95),
    ], start=1):
        for col_j, (_, threshold) in _threshold_checks.items():
            val = row_vals[col_j - 1] if col_j <= len(row_vals) else 0
            ratio = val / threshold if threshold > 0 else 0
            if ratio <= 0.5:
                cell_bg = "#d5f5e3"  # green
            elif ratio <= 1.0:
                cell_bg = "#fdebd0"  # yellow/amber
            else:
                cell_bg = "#fadbd8"  # red
            metrics_table[row_i, col_j].set_facecolor(cell_bg)

    middle_gs = fig.add_gridspec(
        1, 2,
        left=0.06, right=0.97,
        bottom=0.27, top=0.75,
        wspace=0.16,
        width_ratios=[0.9, 1.3],
    )

    # --- Middle-left: Vertically long layer trend plot ---
    ax_err = fig.add_subplot(middle_gs[0, 0])
    layer_idx = np.arange(1, num_layers + 1)
    radial_rmse = np.sqrt(np.array(rmse_x_all) ** 2 + np.array(rmse_y_all) ** 2)
    worst_axis_error = np.maximum(np.array(max_x_all), np.array(max_y_all))

    ax_err.plot(layer_idx, radial_rmse, "-", linewidth=1.0, color="#2c3e50", label="Radial RMSE")
    ax_err.scatter(
        layer_idx,
        radial_rmse,
        c=["#2ecc71" if p else "#e74c3c" for p in pass_flags],
        s=16,
        zorder=3,
    )
    ax_err.plot(
        layer_idx,
        worst_axis_error,
        "--",
        linewidth=0.9,
        color="#e67e22",
        label="Worst axis max",
    )
    ax_err.axhspan(
        0,
        THRESHOLDS["max_abs_diff_mm"],
        alpha=0.10,
        color="#2ecc71",
        label=f"\u2264 {THRESHOLDS['max_abs_diff_mm']} mm target",
    )
    ax_err.set_xlabel("Layer", fontsize=7)
    ax_err.set_ylabel("Error (mm)", fontsize=7)
    ax_err.set_title("Layer Trend", fontsize=9)
    ax_err.tick_params(labelsize=6)
    ax_err.grid(True, alpha=0.3)
    if num_layers > 25:
        ax_err.tick_params(axis="x", rotation=90, labelsize=4)
    ax_err.legend(fontsize=5, loc="upper left")

    # --- Middle-right: All-layer heatmap ---
    right_gs = middle_gs[0, 1].subgridspec(
        3, 1,
        height_ratios=[0.78, 0.13, 0.09],
        hspace=0.18,
    )
    ax_heatmap = fig.add_subplot(right_gs[0, 0])
    ax_heatmap_flags = fig.add_subplot(right_gs[1, 0])
    ax_heatmap_cbar = fig.add_subplot(right_gs[2, 0])
    heatmap_values = np.array([
        np.abs(mean_x_all),
        np.abs(mean_y_all),
        std_x_all,
        std_y_all,
        max_x_all,
        max_y_all,
    ])
    flag_rows = {}
    fallback_flags = []
    never_settled_flags = []
    low_overlap_flags = []
    for layer in layers_data:
        r = layer.get("results", {})
        fallback_flags.append(1 if r.get("filtered_stats_fallback_to_raw", False) else 0)
        never_settled_flags.append(1 if r.get("settling_status") == "never_settled" else 0)
        overlap = r.get("time_overlap_fraction")
        low_overlap_flags.append(1 if overlap is not None and overlap < 0.95 else 0)
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
        ax_heatmap,
        heatmap_values,
        layer_labels,
        ["|mu_x|", "|mu_y|", "std_x", "std_y", "max_x", "max_y"],
        flag_rows=flag_rows if flag_rows else None,
        flag_ax=ax_heatmap_flags,
        cbar_ax=ax_heatmap_cbar,
    )

    # --- Bottom: Warnings and worst-layer summary ---
    bottom_gs = fig.add_gridspec(
        1, 2,
        left=0.06, right=0.97,
        bottom=0.05, top=0.22,
        wspace=0.10,
        width_ratios=[1.2, 1.0],
    )
    ax_filter = fig.add_subplot(bottom_gs[0, 0])
    ax_filter.axis("off")
    _draw_filter_panel(ax_filter, layers_data, report_mode)

    ax_worst = fig.add_subplot(bottom_gs[0, 1])
    ax_worst.axis("off")

    worst_order = np.argsort(worst_axis_error)[::-1][: min(5, num_layers)]
    if len(worst_order) > 0:
        worst_lines = [
            f"L{layer_labels[idx]}: max {worst_axis_error[idx]:.2f} mm, radial {radial_rmse[idx]:.2f} mm"
            for idx in worst_order
        ]
        ax_worst.text(
            0.02,
            0.94,
            "Worst Layers",
            ha="left",
            va="top",
            fontsize=8,
            fontweight="bold",
            transform=ax_worst.transAxes,
        )
        ax_worst.text(
            0.02,
            0.84,
            "\n".join(worst_lines),
            ha="left",
            va="top",
            fontsize=6.5,
            family="monospace",
            transform=ax_worst.transAxes,
        )

    return fig


def _generate_executive_summary(report_data, patient_id, patient_name, report_mode):
    """Generate a single executive summary page covering all beams in the plan."""
    from datetime import date as _date

    fig = plt.figure(figsize=A4_FIGSIZE)

    # Title
    fig.text(
        0.50, 0.97, "Executive Summary",
        ha="center", va="top", fontsize=18, fontweight="bold",
    )

    # Patient info
    info_text = (
        f"Patient ID: {patient_id}    |    "
        f"Name: {patient_name}    |    "
        f"Date: {_date.today().isoformat()}"
    )
    fig.text(
        0.50, 0.935, info_text,
        ha="center", va="top", fontsize=9, color="#555555",
    )

    # Collect per-beam summary data
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
            r = layer.get("results", {})
            mean_x_vals.append(_metric_value(r, "mean_diff_x", report_mode))
            mean_y_vals.append(_metric_value(r, "mean_diff_y", report_mode))
            max_err_vals.append(max(
                _metric_value(r, "max_abs_diff_x", report_mode),
                _metric_value(r, "max_abs_diff_y", report_mode),
            ))
            lp, lt = _spot_pass_summary(r, report_mode=report_mode)
            passed_spots += lp
            total_spots += lt

        pass_rate = passed_spots / total_spots * 100 if total_spots > 0 else 0
        verdict, color = _beam_verdict(pass_rate)
        g_mean_x = np.mean(mean_x_vals) if mean_x_vals else 0
        g_mean_y = np.mean(mean_y_vals) if mean_y_vals else 0
        g_max_err = max(max_err_vals) if max_err_vals else 0

        beam_rows.append({
            "name": beam_name,
            "layers": len(layers_data),
            "pass_rate": pass_rate,
            "passed": passed_spots,
            "total": total_spots,
            "mean_x": g_mean_x,
            "mean_y": g_mean_y,
            "max_err": g_max_err,
            "verdict": verdict,
            "color": color,
        })
        fraction_passed += passed_spots
        fraction_total += total_spots

    # Overall fraction verdict
    fraction_rate = fraction_passed / fraction_total * 100 if fraction_total > 0 else 0
    fraction_verdict, fraction_color = _beam_verdict(fraction_rate)

    # Overall verdict badge
    badge_text = f"{fraction_verdict}  ({fraction_passed}/{fraction_total} spots, {fraction_rate:.0f}%)"
    fig.text(
        0.50, 0.905, badge_text,
        ha="center", va="top", fontsize=13, fontweight="bold", color="white",
        bbox=dict(boxstyle="round,pad=0.4", facecolor=fraction_color, edgecolor="none"),
    )

    # Build summary table
    ax_tbl = fig.add_axes([0.06, 0.40, 0.88, 0.48])
    ax_tbl.axis("off")

    col_labels = ["Beam", "Layers", "Pass Rate", "Mean X (mm)", "Mean Y (mm)",
                  "Max |err| (mm)", "Verdict"]

    table_rows = []
    for b in beam_rows:
        table_rows.append([
            b["name"],
            str(b["layers"]),
            f"{b['passed']}/{b['total']} ({b['pass_rate']:.0f}%)",
            f"{b['mean_x']:+.3f}",
            f"{b['mean_y']:+.3f}",
            f"{b['max_err']:.3f}",
            b["verdict"],
        ])

    if not table_rows:
        ax_tbl.text(0.5, 0.5, "No beam data available",
                    ha="center", va="center", fontsize=12)
        return fig

    table = ax_tbl.table(
        cellText=table_rows, colLabels=col_labels,
        loc="upper center", cellLoc="center",
    )
    table.auto_set_font_size(False)
    num_beams = len(table_rows)
    tbl_fontsize = 9 if num_beams <= 6 else (7 if num_beams <= 12 else 6)
    table.set_fontsize(tbl_fontsize)
    row_scale = min(2.5, max(1.2, 14.0 / (num_beams + 1)))
    table.scale(1.0, row_scale)

    # Style header
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#34495e")
        table[0, j].set_text_props(color="white", fontweight="bold")

    # Color verdict cells and pass rate cells
    for i, b in enumerate(beam_rows):
        row_idx = i + 1
        # Verdict column (last)
        table[row_idx, 6].set_facecolor(b["color"])
        table[row_idx, 6].set_text_props(color="white", fontweight="bold")
        # Pass rate column - light background
        if b["pass_rate"] == 100:
            table[row_idx, 2].set_facecolor("#d5f5e3")
        elif b["pass_rate"] >= 80:
            table[row_idx, 2].set_facecolor("#fdebd0")
        else:
            table[row_idx, 2].set_facecolor("#fadbd8")

    # Footer note
    fig.text(
        0.50, 0.37,
        f"Report mode: {report_mode}    |    Thresholds: "
        f"Mean \u2264{THRESHOLDS['mean_diff_mm']} mm, "
        f"Std \u2264{THRESHOLDS['std_diff_mm']} mm, "
        f"Max \u2264{THRESHOLDS['max_abs_diff_mm']} mm",
        ha="center", va="top", fontsize=7, color="#888888",
    )

    return fig


def generate_report(
    report_data,
    output_dir,
    report_style="summary",
    report_name=None,
    report_mode="raw",
):
    """
    Generates a PDF report with analysis plots organized by beam.

    Args:
        report_data: Dictionary of beam_name -> {'layers': [...]} analysis data.
        output_dir: Directory to write the PDF into.
        report_style: 'summary' for one-page-per-beam dashboard,
                      'classic' for the original multi-page detailed report.
        report_name: Optional PDF filename (without extension). Defaults to 'analysis_report'.
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{report_name}.pdf" if report_name else "analysis_report.pdf"
    pdf_path = os.path.join(output_dir, filename)

    # Extract patient info (stored with underscore-prefix keys to avoid beam name collision)
    patient_id = report_data.get("_patient_id", "")
    patient_name = report_data.get("_patient_name", "")

    with PdfPages(pdf_path) as pdf:
        for beam_name, beam_data in report_data.items():
            if beam_name.startswith("_"):
                continue  # skip metadata keys
            if not beam_data["layers"]:
                logger.warning(
                    f"No layers with analysis results for beam '{beam_name}'. Skipping."
                )
                continue

            if report_style == "summary":
                summary_fig = _generate_summary_page(
                    beam_name,
                    beam_data,
                    patient_id=patient_id,
                    patient_name=patient_name,
                    report_mode=report_mode,
                )
                pdf.savefig(summary_fig)
                plt.close(summary_fig)
                logger.info(f"Summary page for Beam '{beam_name}' added to PDF.")
            else:
                # Classic report: error bar plot + per-layer 2D position plots
                error_bar_fig = _generate_error_bar_plot_for_beam(
                    beam_name,
                    beam_data["layers"],
                    report_mode=report_mode,
                )
                pdf.savefig(error_bar_fig)
                plt.close(error_bar_fig)
                logger.info(f"Plot data for Beam '{beam_name}' added to PDF.")

                all_plan_positions = []
                for layer_data in beam_data["layers"]:
                    results = layer_data.get("results", {})
                    plan_pos = results.get("plan_positions")
                    if plan_pos is not None:
                        all_plan_positions.append(plan_pos)

                if all_plan_positions:
                    all_plan_positions = np.vstack(all_plan_positions)
                    margin = 20  # 2cm margin
                    global_min_coords = all_plan_positions.min(axis=0) - margin
                    global_max_coords = all_plan_positions.max(axis=0) + margin
                else:
                    global_min_coords = np.array([0, 0])
                    global_max_coords = np.array([100, 100])

                layers_list = beam_data["layers"]
                for i in range(0, len(layers_list), 6):
                    batch_layers = layers_list[i : i + 6]
                    layer_plots = []

                    for layer_data in batch_layers:
                        layer_index = layer_data.get("layer_index", 0)
                        results = layer_data.get("results", {})
                        plan_pos = results.get("plan_positions")
                        log_pos = results.get("log_positions")
                        if plan_pos is None or log_pos is None:
                            continue

                        layer_fig = _generate_per_layer_position_plot(
                            plan_pos,
                            log_pos,
                            layer_index,
                            beam_name,
                            global_min_coords,
                            global_max_coords,
                        )
                        layer_plots.append(layer_fig)

                    _save_plots_to_pdf_grid(pdf, layer_plots, beam_name)

    logger.info(f"Analysis report saved to {pdf_path}")
