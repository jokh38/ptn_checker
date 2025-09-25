import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _generate_error_bar_plot(mean_diff, std_diff):
    """Generates an error bar plot figure for x and y position differences."""
    num_layers = len(mean_diff['x'])
    layers = np.arange(1, num_layers + 1)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    # X-position difference plot
    ax1.errorbar(layers, mean_diff['x'], yerr=std_diff['x'], fmt='o-', capsize=5)
    ax1.set_title('X Position Difference (plan - log)')
    ax1.set_xlabel('Layer Number')
    ax1.set_ylabel('Difference (mm)')
    ax1.grid(True)

    # Y-position difference plot
    ax2.errorbar(layers, mean_diff['y'], yerr=std_diff['y'], fmt='o-', capsize=5, color='orange')
    ax2.set_title('Y Position Difference (plan - log)')
    ax2.set_xlabel('Layer Number')
    ax2.set_ylabel('Difference (mm)')
    ax2.grid(True)

    fig.tight_layout()
    return fig

def _generate_position_plot(plan_positions, log_positions):
    """Generates a 2D position comparison plot figure for all layers combined."""
    fig, ax = plt.subplots(figsize=(10, 10))

    plan_labeled = False
    log_labeled = False

    for layer_plan, layer_log in zip(plan_positions, log_positions):
        ax.plot(layer_plan[:, 0], layer_plan[:, 1], 'r-', linewidth=1, label='Plan' if not plan_labeled else "")
        plan_labeled = True

        sampled_log = layer_log[::10]
        ax.scatter(sampled_log[:, 0], sampled_log[:, 1], c='b', marker='+', s=10, label='Log' if not log_labeled else "")
        log_labeled = True

    _setup_plot_axes(ax, '2D Position Comparison (All Layers)')
    return fig

def _setup_plot_axes(ax, title):
    """Helper function to set up common plot attributes."""
    ax.set_xlabel('X Position (mm)')
    ax.set_ylabel('Y Position (mm)')
    ax.set_title(title)
    ax.legend()
    ax.grid(True)
    ax.set_aspect('equal', adjustable='box')

def _generate_per_layer_position_plot(plan_positions, log_positions, layer_index):
    """Generates a 2D position comparison plot figure for a single layer."""
    fig, ax = plt.subplots(figsize=(10, 10))

    ax.plot(plan_positions[:, 0], plan_positions[:, 1], 'r-', linewidth=1, label='Plan')

    sampled_log = log_positions[::10]
    ax.scatter(sampled_log[:, 0], sampled_log[:, 1], c='b', marker='+', s=10, label='Log')

    _setup_plot_axes(ax, f'2D Position Comparison - Layer {layer_index + 1}')
    return fig


def generate_report(plan_data, log_data, output_dir):
    """
    Generates a multi-page PDF report with analysis plots.

    Args:
        plan_data (dict): A dictionary containing data from the treatment plan.
        log_data (dict): A dictionary containing data from the machine logs.
        output_dir (str): The directory where the PDF report will be saved.
    """
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, "analysis_report.pdf")

    with PdfPages(pdf_path) as pdf:
        # 1. Generate and save the error bar plot
        if 'mean_diff' in plan_data and 'std_diff' in plan_data:
            error_bar_fig = _generate_error_bar_plot(plan_data['mean_diff'], plan_data['std_diff'])
            pdf.savefig(error_bar_fig)
            plt.close(error_bar_fig)
            logger.info("Error bar plot added to PDF.")
        else:
            logger.warning("Mean/Std difference data not available for error bar plot.")

        # 2. Generate and save the combined 2D position comparison plot
        if 'positions' in plan_data and 'positions' in log_data:
            position_fig = _generate_position_plot(plan_data['positions'], log_data['positions'])
            pdf.savefig(position_fig)
            plt.close(position_fig)
            logger.info("Combined position comparison plot added to PDF.")

            # 3. Generate and save per-layer 2D position plots
            for i, (plan_pos, log_pos) in enumerate(zip(plan_data['positions'], log_data['positions'])):
                layer_fig = _generate_per_layer_position_plot(plan_pos, log_pos, i)
                pdf.savefig(layer_fig)
                plt.close(layer_fig)
                logger.info(f"Layer {i+1} position plot added to PDF.")
        else:
            logger.warning("Position data not available for 2D position plot.")

    logger.info(f"Analysis report saved to {pdf_path}")