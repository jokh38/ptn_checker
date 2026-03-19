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


def _generate_error_bar_plot_for_beam(beam_name, layers_data):
    """Generates an error bar plot figure for a single beam."""
    num_layers = len(layers_data)
    layer_indices = np.arange(1, num_layers + 1)
    mean_diff_x = [
        layer.get("results", {}).get("mean_diff_x", 0) for layer in layers_data
    ]
    mean_diff_y = [
        layer.get("results", {}).get("mean_diff_y", 0) for layer in layers_data
    ]
    std_diff_x = [
        layer.get("results", {}).get("std_diff_x", 0) for layer in layers_data
    ]
    std_diff_y = [
        layer.get("results", {}).get("std_diff_y", 0) for layer in layers_data
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


def _layer_passes(results):
    """Check whether a single layer's results are within thresholds."""
    mean_ok = (
        abs(results.get("mean_diff_x", 0)) <= THRESHOLDS["mean_diff_mm"]
        and abs(results.get("mean_diff_y", 0)) <= THRESHOLDS["mean_diff_mm"]
    )
    std_ok = (
        results.get("std_diff_x", 0) <= THRESHOLDS["std_diff_mm"]
        and results.get("std_diff_y", 0) <= THRESHOLDS["std_diff_mm"]
    )
    max_ok = (
        results.get("max_abs_diff_x", 0) <= THRESHOLDS["max_abs_diff_mm"]
        and results.get("max_abs_diff_y", 0) <= THRESHOLDS["max_abs_diff_mm"]
    )
    return mean_ok and std_ok and max_ok


def _generate_summary_page(beam_name, beam_data):
    """
    Generates a one-page A4 summary dashboard for a single beam.

    Layout:
        Header text area (top): beam name, layer count, pass rate, global metrics
        Top-left: Combined X+Y error bar plot with tolerance band
        Top-right: Layer heatmap (layers x 4 metrics) with RdYlGn_r colormap
        Bottom-left: Pooled histogram of diff_x/diff_y with Gaussian fit
        Bottom-right: Table of flagged layers (or "All layers within tolerance")
    """
    layers_data = beam_data["layers"]
    num_layers = len(layers_data)

    # --- Collect per-layer metrics ---
    mean_x_all, mean_y_all = [], []
    std_x_all, std_y_all = [], []
    rmse_x_all, rmse_y_all = [], []
    max_x_all, max_y_all = [], []
    all_diff_x, all_diff_y = [], []
    all_plan_pos, all_log_pos = [], []
    pass_flags = []
    layer_labels = []

    for layer in layers_data:
        r = layer.get("results", {})
        layer_labels.append(str(layer.get("layer_index", "?")))

        mean_x_all.append(r.get("mean_diff_x", 0))
        mean_y_all.append(r.get("mean_diff_y", 0))
        std_x_all.append(r.get("std_diff_x", 0))
        std_y_all.append(r.get("std_diff_y", 0))
        rmse_x_all.append(r.get("rmse_x", 0))
        rmse_y_all.append(r.get("rmse_y", 0))
        max_x_all.append(r.get("max_abs_diff_x", 0))
        max_y_all.append(r.get("max_abs_diff_y", 0))

        if "diff_x" in r:
            all_diff_x.append(r["diff_x"])
        if "diff_y" in r:
            all_diff_y.append(r["diff_y"])

        plan_pos = r.get("plan_positions")
        log_pos = r.get("log_positions")
        if plan_pos is not None:
            all_plan_pos.append(plan_pos)
        if log_pos is not None:
            all_log_pos.append(log_pos)

        pass_flags.append(_layer_passes(r))

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

    # Similarity index: Pearson correlation of concatenated plan vs log positions
    similarity_str = "N/A"
    if all_plan_pos and all_log_pos:
        plan_concat = np.vstack(all_plan_pos).ravel()
        log_concat = np.vstack(all_log_pos).ravel()
        if len(plan_concat) == len(log_concat) and len(plan_concat) > 1:
            corr, _ = pearsonr(plan_concat, log_concat)
            similarity_str = f"{corr:.6f}"

    # --- Build the figure ---
    fig = plt.figure(figsize=A4_FIGSIZE)

    # Reserve top 18% for header, bottom 82% for 2x2 grid
    header_height = 0.18
    grid_bottom = 0.04
    grid_top = 1.0 - header_height - 0.02

    # Header text
    pass_color = (
        "#2ecc71" if pass_rate == 100 else ("#e67e22" if pass_rate >= 80 else "#e74c3c")
    )
    header_lines = (
        f"{beam_name}    |    Layers: {num_layers}    |    "
        f"Pass rate: {num_pass}/{num_layers} ({pass_rate:.0f}%)\n"
        f"Mean X/Y: {global_mean_x:+.3f} / {global_mean_y:+.3f} mm    "
        f"Std X/Y: {global_std_x:.3f} / {global_std_y:.3f} mm    "
        f"RMSE X/Y: {global_rmse_x:.3f} / {global_rmse_y:.3f} mm\n"
        f"Max |err| X/Y: {global_max_x:.3f} / {global_max_y:.3f} mm    "
        f"Similarity (Pearson r): {similarity_str}"
    )
    fig.text(
        0.5,
        1.0 - header_height / 2,
        header_lines,
        ha="center",
        va="center",
        fontsize=9,
        family="monospace",
        bbox=dict(
            boxstyle="round,pad=0.5",
            facecolor="#f0f0f0",
            edgecolor=pass_color,
            linewidth=2,
        ),
    )

    # 2x2 subplot grid
    gs = fig.add_gridspec(
        2,
        2,
        left=0.10,
        right=0.95,
        bottom=grid_bottom,
        top=grid_top,
        hspace=0.35,
        wspace=0.30,
    )

    # --- Top-left: Error bar plot (X and Y combined) ---
    ax_err = fig.add_subplot(gs[0, 0])
    layer_idx = np.arange(1, num_layers + 1)
    ax_err.errorbar(
        layer_idx,
        mean_x_all,
        yerr=std_x_all,
        fmt="o-",
        capsize=3,
        markersize=3,
        linewidth=0.8,
        label="X",
        color="#3498db",
    )
    ax_err.errorbar(
        layer_idx,
        mean_y_all,
        yerr=std_y_all,
        fmt="s-",
        capsize=3,
        markersize=3,
        linewidth=0.8,
        label="Y",
        color="#e67e22",
    )
    tol = THRESHOLDS["mean_diff_mm"]
    ax_err.axhspan(-tol, tol, alpha=0.12, color="green", label=f"±{tol} mm tol.")
    ax_err.set_xlabel("Layer", fontsize=7)
    ax_err.set_ylabel("Mean diff (mm)", fontsize=7)
    ax_err.set_title("Position Error by Layer", fontsize=8)
    ax_err.legend(fontsize=6, loc="upper right")
    ax_err.tick_params(labelsize=6)
    ax_err.grid(True, alpha=0.3)

    # --- Top-right: Layer heatmap ---
    ax_heat = fig.add_subplot(gs[0, 1])
    heatmap_data = np.column_stack(
        [np.abs(mean_x_all), np.abs(mean_y_all), std_x_all, std_y_all]
    )  # shape: (num_layers, 4)
    if num_layers > 0:
        im = ax_heat.imshow(
            heatmap_data.T,
            aspect="auto",
            cmap="RdYlGn_r",
            norm=Normalize(vmin=0, vmax=THRESHOLDS["max_abs_diff_mm"]),
        )
        ax_heat.set_yticks([0, 1, 2, 3])
        ax_heat.set_yticklabels(["|mean_x|", "|mean_y|", "std_x", "std_y"], fontsize=6)
        ax_heat.set_xlabel("Layer", fontsize=7)
        ax_heat.set_title("Metrics Heatmap", fontsize=8)
        ax_heat.tick_params(labelsize=6)
        # Show layer numbers on x-axis (subsample if too many)
        if num_layers <= 30:
            ax_heat.set_xticks(range(num_layers))
            ax_heat.set_xticklabels(layer_labels, fontsize=5, rotation=90)
        else:
            step = max(1, num_layers // 20)
            ticks = list(range(0, num_layers, step))
            ax_heat.set_xticks(ticks)
            ax_heat.set_xticklabels(
                [layer_labels[i] for i in ticks], fontsize=5, rotation=90
            )
        fig.colorbar(im, ax=ax_heat, fraction=0.046, pad=0.04).ax.tick_params(
            labelsize=6
        )
    else:
        ax_heat.text(
            0.5, 0.5, "No data", ha="center", va="center", transform=ax_heat.transAxes
        )

    # --- Bottom-left: Pooled histogram with Gaussian fit ---
    ax_hist = fig.add_subplot(gs[1, 0])
    if all_diff_x and all_diff_y:
        pooled_x = np.concatenate(all_diff_x)
        pooled_y = np.concatenate(all_diff_y)
        bins = np.arange(-5, 5.01, 0.05)
        ax_hist.hist(
            pooled_x, bins=bins, density=True, alpha=0.5, color="#3498db", label="X"
        )
        ax_hist.hist(
            pooled_y, bins=bins, density=True, alpha=0.5, color="#e67e22", label="Y"
        )
        bin_centers = (bins[:-1] + bins[1:]) / 2
        for pooled, color, label in [
            (pooled_x, "#3498db", "X fit"),
            (pooled_y, "#e67e22", "Y fit"),
        ]:
            hist_vals, _ = np.histogram(pooled, bins=bins, density=True)
            try:
                popt, _ = curve_fit(_gaussian, bin_centers, hist_vals, p0=[1, 0, 1])
                ax_hist.plot(
                    bin_centers,
                    _gaussian(bin_centers, *popt),
                    "-",
                    color=color,
                    linewidth=1.5,
                    label=f"{label} (μ={popt[1]:.2f}, σ={abs(popt[2]):.2f})",
                )
            except RuntimeError:
                logger.debug(f"Gaussian fit failed for {label}, skipping fit curve")
        ax_hist.legend(fontsize=5, loc="upper right")
    ax_hist.set_xlabel("Difference (mm)", fontsize=7)
    ax_hist.set_ylabel("Density", fontsize=7)
    ax_hist.set_title("Pooled Error Distribution", fontsize=8)
    ax_hist.tick_params(labelsize=6)
    ax_hist.grid(True, alpha=0.3)

    # --- Bottom-right: Flagged layers table ---
    ax_tbl = fig.add_subplot(gs[1, 1])
    ax_tbl.axis("off")
    flagged_rows = []
    for i, layer in enumerate(layers_data):
        if not pass_flags[i]:
            r = layer.get("results", {})
            flagged_rows.append(
                [
                    layer_labels[i],
                    f"{r.get('mean_diff_x', 0):+.2f}",
                    f"{r.get('mean_diff_y', 0):+.2f}",
                    f"{r.get('std_diff_x', 0):.2f}",
                    f"{r.get('std_diff_y', 0):.2f}",
                    f"{r.get('max_abs_diff_x', 0):.2f}",
                    f"{r.get('max_abs_diff_y', 0):.2f}",
                ]
            )

    if flagged_rows:
        col_labels = ["Layer", "μ_x", "μ_y", "σ_x", "σ_y", "max_x", "max_y"]
        # Limit displayed rows to avoid overflow
        display_rows = flagged_rows[:15]
        table = ax_tbl.table(
            cellText=display_rows, colLabels=col_labels, loc="center", cellLoc="center"
        )
        table.auto_set_font_size(False)
        table.set_fontsize(6)
        table.scale(1.0, 1.2)
        # Color header
        for j in range(len(col_labels)):
            table[0, j].set_facecolor("#e74c3c")
            table[0, j].set_text_props(color="white", fontweight="bold")
        title_suffix = (
            f" (showing 15 of {len(flagged_rows)})" if len(flagged_rows) > 15 else ""
        )
        ax_tbl.set_title(f"Flagged Layers{title_suffix}", fontsize=8, color="#e74c3c")
    else:
        ax_tbl.text(
            0.5,
            0.5,
            "All layers within tolerance",
            ha="center",
            va="center",
            fontsize=12,
            color="#2ecc71",
            fontweight="bold",
            transform=ax_tbl.transAxes,
        )
        ax_tbl.set_title("Flagged Layers", fontsize=8, color="#2ecc71")

    return fig


def generate_report(report_data, output_dir, report_style="summary"):
    """
    Generates a PDF report with analysis plots organized by beam.

    Args:
        report_data: Dictionary of beam_name -> {'layers': [...]} analysis data.
        output_dir: Directory to write the PDF into.
        report_style: 'summary' for one-page-per-beam dashboard,
                      'classic' for the original multi-page detailed report.
    """
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, "analysis_report.pdf")

    with PdfPages(pdf_path) as pdf:
        for beam_name, beam_data in report_data.items():
            if not beam_data["layers"]:
                logger.warning(
                    f"No layers with analysis results for beam '{beam_name}'. Skipping."
                )
                continue

            if report_style == "summary":
                summary_fig = _generate_summary_page(beam_name, beam_data)
                pdf.savefig(summary_fig)
                plt.close(summary_fig)
                logger.info(f"Summary page for Beam '{beam_name}' added to PDF.")
            else:
                # Classic report: error bar plot + per-layer 2D position plots
                error_bar_fig = _generate_error_bar_plot_for_beam(
                    beam_name, beam_data["layers"]
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
