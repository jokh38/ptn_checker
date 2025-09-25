import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _generate_error_bar_plot_for_beam(beam_name, layers_data):
    """Generates an error bar plot figure for a single beam."""
    num_layers = len(layers_data)
    layer_indices = [layer['layer_index'] for layer in layers_data]
    mean_diff_x = [layer['results']['mean_diff_x'] for layer in layers_data]
    mean_diff_y = [layer['results']['mean_diff_y'] for layer in layers_data]
    std_diff_x = [layer['results']['std_diff_x'] for layer in layers_data]
    std_diff_y = [layer['results']['std_diff_y'] for layer in layers_data]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.27, 11.69))
    fig.suptitle(f'Position Difference (plan - log) - {beam_name}', fontsize=16)

    # X-position difference plot
    ax1.errorbar(layer_indices, mean_diff_x, yerr=std_diff_x, fmt='o-', capsize=5)
    ax1.set_title('X Position Difference')
    ax1.set_xlabel('Layer Number')
    ax1.set_ylabel('Difference (mm)')
    ax1.grid(True)

    # Y-position difference plot
    ax2.errorbar(layer_indices, mean_diff_y, yerr=std_diff_y, fmt='o-', capsize=5, color='orange')
    ax2.set_title('Y Position Difference')
    ax2.set_xlabel('Layer Number')
    ax2.set_ylabel('Difference (mm)')
    ax2.grid(True)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return fig

def _generate_per_layer_position_plot(plan_positions, log_positions, layer_index, beam_name, global_min_coords, global_max_coords):
    """Generates a 2D position comparison plot figure for a single layer with outlier rejection."""

    # Filter log positions
    filtered_log_positions = log_positions[
        (log_positions[:, 0] >= global_min_coords[0]) & (log_positions[:, 0] <= global_max_coords[0]) &
        (log_positions[:, 1] >= global_min_coords[1]) & (log_positions[:, 1] <= global_max_coords[1])
    ]

    fig, ax = plt.subplots(figsize=(8, 8))

    ax.plot(plan_positions[:, 0], plan_positions[:, 1], 'r-', linewidth=1, label='Plan')

    if filtered_log_positions.size > 0:
        sampled_log = filtered_log_positions[::10] if len(filtered_log_positions) > 10 else filtered_log_positions
        ax.scatter(sampled_log[:, 0], sampled_log[:, 1], c='b', marker='+', s=10, label='Log')
    else:
        logger.warning(f"No log data within the margin for layer {layer_index} of {beam_name}.")

    ax.set_xlabel('X Position (mm)')
    ax.set_ylabel('Y Position (mm)')
    ax.set_title(f'2D Position - Layer {layer_index + 1}')
    ax.legend()
    ax.grid(True)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xlim(global_min_coords[0], global_max_coords[0])
    ax.set_ylim(global_min_coords[1], global_max_coords[1])

    return fig

def _save_plots_to_pdf_grid(pdf, plots, beam_name):
    """Saves up to 6 plots to a single PDF page in a 3x2 grid."""
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.suptitle(f'2D Position Comparison - {beam_name}', fontsize=16)

    for i, plot_fig in enumerate(plots):
        if i >= 6:
            break

        # This is a workaround to copy the content of the existing plot figure to a subplot
        ax_src = plot_fig.axes[0]
        ax_dest = fig.add_subplot(3, 2, i + 1)

        for line in ax_src.get_lines():
            ax_dest.plot(line.get_xdata(), line.get_ydata(), color=line.get_color(),
                         linestyle=line.get_linestyle(), linewidth=line.get_linewidth(),
                         label=line.get_label())

        for collection in ax_src.collections:
             ax_dest.scatter(collection.get_offsets()[:, 0], collection.get_offsets()[:, 1],
                           c=collection.get_facecolors(), marker=collection.get_paths()[0],
                           s=collection.get_sizes(), label=collection.get_label())

        ax_dest.set_title(ax_src.get_title())
        ax_dest.set_xlabel(ax_src.get_xlabel())
        ax_dest.set_ylabel(ax_src.get_ylabel())
        ax_dest.grid(True)
        ax_dest.legend()
        ax_dest.set_aspect('equal', adjustable='box')
        ax_dest.set_xlim(ax_src.get_xlim())
        ax_dest.set_ylim(ax_src.get_ylim())

        plt.close(plot_fig) # Close the original figure to save memory

    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    pdf.savefig(fig)
    plt.close(fig)

def generate_report(report_data, output_dir):
    """
    Generates a multi-page PDF report with analysis plots organized by beam.
    """
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, "analysis_report.pdf")

    with PdfPages(pdf_path) as pdf:
        for beam_name, beam_data in report_data.items():
            if not beam_data['layers']:
                logger.warning(f"No layers with analysis results for beam '{beam_name}'. Skipping.")
                continue

            # 1. Generate and save the error bar plot for the beam
            error_bar_fig = _generate_error_bar_plot_for_beam(beam_name, beam_data['layers'])
            pdf.savefig(error_bar_fig)
            plt.close(error_bar_fig)
            logger.info(f"Error bar plot for beam '{beam_name}' added to PDF.")

            # 2. Calculate global coordinate bounds for the beam
            all_plan_positions = []
            for layer_data in beam_data['layers']:
                plan_pos = layer_data['results']['plan_positions']
                all_plan_positions.append(plan_pos)

            if all_plan_positions:
                all_plan_positions = np.vstack(all_plan_positions)
                margin = 20  # 2cm margin
                global_min_coords = all_plan_positions.min(axis=0) - margin
                global_max_coords = all_plan_positions.max(axis=0) + margin
            else:
                global_min_coords = np.array([0, 0])
                global_max_coords = np.array([100, 100])

            # 3. Generate and save per-layer 2D position plots in batches of 6
            layers_list = beam_data['layers']
            for i in range(0, len(layers_list), 6):
                batch_layers = layers_list[i:i+6]
                layer_plots = []

                for layer_data in batch_layers:
                    layer_index = layer_data['layer_index']
                    plan_pos = layer_data['results']['plan_positions']
                    log_pos = layer_data['results']['log_positions']

                    layer_fig = _generate_per_layer_position_plot(plan_pos, log_pos, layer_index, beam_name, global_min_coords, global_max_coords)
                    layer_plots.append(layer_fig)

                # Save this batch to PDF and immediately close the figures
                _save_plots_to_pdf_grid(pdf, layer_plots, beam_name)

    logger.info(f"Analysis report saved to {pdf_path}")