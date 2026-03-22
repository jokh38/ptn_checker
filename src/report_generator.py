import logging
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from src.report_constants import A4_FIGSIZE, POSITION_PLOT_FIGSIZE
from src.report_layout import (
    _beam_verdict,
    _draw_analysis_info_panel,
    _draw_layer_heatmap,
    _generate_executive_summary,
    _generate_summary_page,
)
from src.report_metrics import (
    THRESHOLDS,
    layer_passes as _layer_passes,
    metric_value as _metric_value,
    spot_pass_summary as _spot_pass_summary,
)


logger = logging.getLogger(__name__)


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
    ax1.errorbar(layer_indices, mean_diff_x, yerr=std_diff_x, fmt="o-", capsize=5)
    ax1.set_title("X Position Difference")
    ax1.set_xlabel("Layer Number")
    ax1.set_ylabel("Difference (mm)")
    ax1.grid(True)
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
    filtered_log_positions = log_positions[
        (log_positions[:, 0] >= global_min_coords[0])
        & (log_positions[:, 0] <= global_max_coords[0])
        & (log_positions[:, 1] >= global_min_coords[1])
        & (log_positions[:, 1] <= global_max_coords[1])
    ]
    fig, ax = plt.subplots(figsize=POSITION_PLOT_FIGSIZE)
    ax.plot(plan_positions[:, 0], plan_positions[:, 1], "r-", linewidth=1, label="Plan")
    if filtered_log_positions.size > 0:
        sampled_log = filtered_log_positions[::10] if len(filtered_log_positions) > 10 else filtered_log_positions
        ax.scatter(sampled_log[:, 0], sampled_log[:, 1], c="b", marker="+", s=10, label="Log")
    else:
        logger.warning("No log data within the margin for layer %s of %s.", layer_index, beam_name)
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
    for idx, plot_fig in enumerate(plots):
        if idx >= 6:
            break
        ax_src = plot_fig.axes[0]
        ax_dest = fig.add_subplot(3, 2, idx + 1)
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
        plt.close(plot_fig)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    pdf.savefig(fig)
    plt.close(fig)


def generate_report(
    report_data,
    output_dir,
    report_style="summary",
    report_name=None,
    report_mode="raw",
    analysis_config=None,
):
    """Generate a PDF report with analysis plots organized by beam."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{report_name}.pdf" if report_name else "analysis_report.pdf"
    pdf_path = os.path.join(output_dir, filename)
    patient_id = report_data.get("_patient_id", "")
    patient_name = report_data.get("_patient_name", "")

    with PdfPages(pdf_path) as pdf:
        for beam_name, beam_data in report_data.items():
            if beam_name.startswith("_"):
                continue
            if not beam_data["layers"]:
                logger.warning("No layers with analysis results for beam '%s'. Skipping.", beam_name)
                continue

            if report_style == "summary":
                summary_fig = _generate_summary_page(
                    beam_name,
                    beam_data,
                    patient_id=patient_id,
                    patient_name=patient_name,
                    report_mode=report_mode,
                    analysis_config=analysis_config,
                )
                pdf.savefig(summary_fig)
                plt.close(summary_fig)
                logger.info("Summary page for Beam '%s' added to PDF.", beam_name)
                continue

            error_bar_fig = _generate_error_bar_plot_for_beam(
                beam_name,
                beam_data["layers"],
                report_mode=report_mode,
            )
            pdf.savefig(error_bar_fig)
            plt.close(error_bar_fig)
            logger.info("Plot data for Beam '%s' added to PDF.", beam_name)

            all_plan_positions = []
            for layer_data in beam_data["layers"]:
                results = layer_data.get("results", {})
                plan_pos = results.get("plan_positions")
                if plan_pos is not None:
                    all_plan_positions.append(plan_pos)

            if all_plan_positions:
                all_plan_positions = np.vstack(all_plan_positions)
                margin = 20
                global_min_coords = all_plan_positions.min(axis=0) - margin
                global_max_coords = all_plan_positions.max(axis=0) + margin
            else:
                global_min_coords = np.array([0, 0])
                global_max_coords = np.array([100, 100])

            layers_list = beam_data["layers"]
            for start_idx in range(0, len(layers_list), 6):
                batch_layers = layers_list[start_idx:start_idx + 6]
                layer_plots = []
                for layer_data in batch_layers:
                    layer_index = layer_data.get("layer_index", 0)
                    results = layer_data.get("results", {})
                    plan_pos = results.get("plan_positions")
                    log_pos = results.get("log_positions")
                    if plan_pos is None or log_pos is None:
                        continue
                    layer_plots.append(
                        _generate_per_layer_position_plot(
                            plan_pos,
                            log_pos,
                            layer_index,
                            beam_name,
                            global_min_coords,
                            global_max_coords,
                        )
                    )
                _save_plots_to_pdf_grid(pdf, layer_plots, beam_name)

    logger.info("Analysis report saved to %s", pdf_path)
