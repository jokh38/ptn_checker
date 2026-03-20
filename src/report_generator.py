import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import Normalize
import numpy as np
from scipy.stats import pearsonr
from scipy.optimize import curve_fit
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


def _gaussian(x, amplitude, mean, stddev):
    """Gaussian function for histogram fitting."""
    return amplitude * np.exp(-(((x - mean) / stddev) ** 2) / 2)


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
        Title bar (top): large beam name + pass/fail badge
        Info row: Patient ID, Patient Name, Date, Layer count
        Metrics table: 2-row table (X/Y) with Mean, Std, RMSE, Max, P95 + Similarity
        2x2 plot grid:
            Top-left: Combined X+Y error bar plot with tolerance band
            Top-right: Layer heatmap (layers x 4 metrics) with RdYlGn_r colormap
            Bottom-left: Pooled histogram of diff_x/diff_y with Gaussian fit
            Bottom-right: Table of flagged layers (or "All layers within tolerance")
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
    all_diff_x, all_diff_y = [], []
    all_plan_pos, all_log_pos = [], []
    pass_flags = []
    layer_labels = []

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

        diff_x_key = _metric_key(r, "diff_x", report_mode)
        diff_y_key = _metric_key(r, "diff_y", report_mode)
        if diff_x_key in r:
            all_diff_x.append(r[diff_x_key])
        if diff_y_key in r:
            all_diff_y.append(r[diff_y_key])

        plan_pos = r.get("plan_positions")
        log_pos = r.get("log_positions")
        if plan_pos is not None:
            all_plan_pos.append(plan_pos)
        if log_pos is not None:
            all_log_pos.append(log_pos)

        pass_flags.append(_layer_passes(r, report_mode=report_mode))

    num_pass = sum(pass_flags)
    pass_rate = num_pass / num_layers * 100 if num_layers > 0 else 0

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

    pass_color = (
        "#2ecc71" if pass_rate == 100 else ("#e67e22" if pass_rate >= 80 else "#e74c3c")
    )

    # --- Build the figure ---
    fig = plt.figure(figsize=A4_FIGSIZE)

    # Layout: title (top 4%), info row (3%), metrics table (12%), plots (remaining)
    # -- Title bar --
    fig.text(
        0.50, 0.97, beam_name,
        ha="center", va="top", fontsize=16, fontweight="bold",
    )
    # Pass rate badge
    badge_text = f"PASS {num_pass}/{num_layers} ({pass_rate:.0f}%)"
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

    # -- Metrics table panel --
    ax_metrics = fig.add_axes([0.08, 0.855, 0.84, 0.07])
    ax_metrics.axis("off")
    col_labels = ["", "Mean (mm)", "Std (mm)", "RMSE (mm)", "Max |err| (mm)", "P95 (mm)", "Similarity (r)"]
    row_x = ["X", f"{global_mean_x:+.3f}", f"{global_std_x:.3f}", f"{global_rmse_x:.3f}",
             f"{global_max_x:.3f}", f"{global_p95_x:.3f}", similarity_str]
    row_y = ["Y", f"{global_mean_y:+.3f}", f"{global_std_y:.3f}", f"{global_rmse_y:.3f}",
             f"{global_max_y:.3f}", f"{global_p95_y:.3f}", ""]
    metrics_table = ax_metrics.table(
        cellText=[row_x, row_y], colLabels=col_labels,
        loc="center", cellLoc="center",
    )
    metrics_table.auto_set_font_size(False)
    metrics_table.set_fontsize(7)
    metrics_table.scale(1.0, 1.4)
    # Style header row
    for j in range(len(col_labels)):
        metrics_table[0, j].set_facecolor("#34495e")
        metrics_table[0, j].set_text_props(color="white", fontweight="bold")
    # Style axis label cells
    metrics_table[1, 0].set_facecolor("#3498db")
    metrics_table[1, 0].set_text_props(color="white", fontweight="bold")
    metrics_table[2, 0].set_facecolor("#e67e22")
    metrics_table[2, 0].set_text_props(color="white", fontweight="bold")

    # Layout: left column (2 plots stacked), right column (full-height colored layer table)
    gs = fig.add_gridspec(
        2, 2,
        left=0.08, right=0.97,
        bottom=0.04, top=0.83,
        hspace=0.30, wspace=0.25,
        width_ratios=[1, 1.2],
    )

    # --- Left-top: Error bar plot (X and Y combined) ---
    ax_err = fig.add_subplot(gs[0, 0])
    layer_idx = np.arange(1, num_layers + 1)
    ax_err.errorbar(
        layer_idx, mean_x_all, yerr=std_x_all,
        fmt="o-", capsize=3, markersize=3, linewidth=0.8,
        label="X", color="#3498db",
    )
    ax_err.errorbar(
        layer_idx, mean_y_all, yerr=std_y_all,
        fmt="s-", capsize=3, markersize=3, linewidth=0.8,
        label="Y", color="#e67e22",
    )
    tol = THRESHOLDS["mean_diff_mm"]
    ax_err.axhspan(-tol, tol, alpha=0.12, color="green", label=f"\u00b1{tol} mm tol.")
    ax_err.set_xlabel("Layer", fontsize=7)
    ax_err.set_ylabel("Mean diff (mm)", fontsize=7)
    ax_err.set_title("Position Error by Layer", fontsize=8)
    ax_err.legend(fontsize=6, loc="upper right")
    ax_err.tick_params(labelsize=6)
    ax_err.grid(True, alpha=0.3)

    # --- Left-bottom: Pooled histogram with Gaussian fit ---
    ax_hist = fig.add_subplot(gs[1, 0])
    if all_diff_x and all_diff_y:
        pooled_x = np.concatenate(all_diff_x)
        pooled_y = np.concatenate(all_diff_y)
        bins = np.arange(-5, 5.01, 0.05)
        hist_min = bins[0]
        hist_max = bins[-1]
        in_range_series = [
            ("X", pooled_x[(pooled_x >= hist_min) & (pooled_x <= hist_max)], "#3498db"),
            ("Y", pooled_y[(pooled_y >= hist_min) & (pooled_y <= hist_max)], "#e67e22"),
        ]
        for axis_label, in_range_values, color in in_range_series:
            if in_range_values.size == 0:
                logger.debug(
                    f"Skipping summary histogram for {axis_label}: no values within [{hist_min}, {hist_max}] mm"
                )
                continue
            ax_hist.hist(
                in_range_values,
                bins=bins,
                density=True,
                alpha=0.5,
                color=color,
                label=axis_label,
            )
        bin_centers = (bins[:-1] + bins[1:]) / 2
        for pooled, color, lbl in [
            (pooled_x, "#3498db", "X fit"),
            (pooled_y, "#e67e22", "Y fit"),
        ]:
            pooled_in_range = pooled[(pooled >= hist_min) & (pooled <= hist_max)]
            if pooled_in_range.size == 0:
                continue
            hist_vals, _ = np.histogram(pooled_in_range, bins=bins, density=True)
            if not np.isfinite(hist_vals).all() or np.sum(hist_vals) <= 0:
                continue
            try:
                popt, _ = curve_fit(_gaussian, bin_centers, hist_vals, p0=[1, 0, 1])
                ax_hist.plot(
                    bin_centers, _gaussian(bin_centers, *popt), "-",
                    color=color, linewidth=1.5,
                    label=f"{lbl} (\u03bc={popt[1]:.2f}, \u03c3={abs(popt[2]):.2f})",
                )
            except RuntimeError:
                logger.debug(f"Gaussian fit failed for {lbl}, skipping fit curve")
        ax_hist.legend(fontsize=5, loc="upper right")
    ax_hist.set_xlabel("Difference (mm)", fontsize=7)
    ax_hist.set_ylabel("Density", fontsize=7)
    ax_hist.set_title("Pooled Error Distribution", fontsize=8)
    ax_hist.tick_params(labelsize=6)
    ax_hist.grid(True, alpha=0.3)

    # --- Right (full height): Colored layer metrics table (top-aligned) ---
    ax_layer_tbl = fig.add_subplot(gs[:, 1])
    ax_layer_tbl.axis("off")
    ax_layer_tbl.set_title("Layer Metrics (mm)", fontsize=9, fontweight="bold", pad=8)

    cmap = plt.cm.RdYlGn_r
    norm = Normalize(vmin=0, vmax=THRESHOLDS["max_abs_diff_mm"])

    # Columns: colormap applies to |μ_x|, |μ_y|, σ_x, σ_y only (indices 1-4)
    col_labels = ["Lyr", "|μ_x|", "|μ_y|", "σ_x", "σ_y", "max_x", "max_y"]
    colored_col_indices = {1, 2, 3, 4}  # columns that get colormap coloring
    table_rows = []
    table_values = []  # raw float values for coloring
    for i in range(num_layers):
        abs_mx = abs(mean_x_all[i])
        abs_my = abs(mean_y_all[i])
        sx = std_x_all[i]
        sy = std_y_all[i]
        mx = max_x_all[i]
        my = max_y_all[i]
        table_rows.append([
            layer_labels[i],
            f"{abs_mx:.2f}", f"{abs_my:.2f}",
            f"{sx:.2f}", f"{sy:.2f}",
            f"{mx:.2f}", f"{my:.2f}",
        ])
        table_values.append([0, abs_mx, abs_my, sx, sy, mx, my])

    if num_layers > 0:
        table = ax_layer_tbl.table(
            cellText=table_rows, colLabels=col_labels,
            loc="upper center", cellLoc="center",
        )
        table.auto_set_font_size(False)
        # Scale font based on layer count to fit page
        if num_layers <= 20:
            tbl_fontsize = 6
        elif num_layers <= 40:
            tbl_fontsize = 5
        else:
            tbl_fontsize = 4
        table.set_fontsize(tbl_fontsize)
        # Scale row height to fit available space
        row_scale = min(1.8, max(0.6, 28.0 / (num_layers + 1)))
        table.scale(1.0, row_scale)

        # Style header row
        for j in range(len(col_labels)):
            table[0, j].set_facecolor("#34495e")
            table[0, j].set_text_props(color="white", fontweight="bold")

        # Color data cells by value (colormap on mean/std only, not max)
        for i in range(num_layers):
            row_idx = i + 1  # +1 because row 0 is header
            vals = table_values[i]
            passed = pass_flags[i]
            # Layer number column: green if pass, red if fail
            table[row_idx, 0].set_facecolor("#d5f5e3" if passed else "#fadbd8")
            table[row_idx, 0].set_text_props(fontweight="bold")
            for j in range(1, len(col_labels)):
                if j in colored_col_indices:
                    rgba = cmap(norm(vals[j]))
                    table[row_idx, j].set_facecolor(rgba)
                    luminance = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
                    text_color = "white" if luminance < 0.5 else "black"
                    table[row_idx, j].set_text_props(color=text_color)
                # max columns (5, 6): no colormap, keep default white background

        # Add colorbar legend just beneath the layer metrics table
        renderer = fig.canvas.get_renderer()
        tbl_window_bbox = table.get_window_extent(renderer)
        tbl_fig_bbox = tbl_window_bbox.transformed(fig.transFigure.inverted())
        cbar_ax = fig.add_axes([
            tbl_fig_bbox.x0 + 0.02, tbl_fig_bbox.y0 - 0.018,
            tbl_fig_bbox.width - 0.04, 0.012,
        ])
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal")
        cbar.ax.tick_params(labelsize=5)
        cbar.set_label("Colormap: |mean|, std  (0 \u2013 3 mm)", fontsize=6)
    else:
        ax_layer_tbl.text(
            0.5, 0.5, "No layer data",
            ha="center", va="center", fontsize=10, transform=ax_layer_tbl.transAxes,
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
