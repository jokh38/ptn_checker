import matplotlib.pyplot as plt
import numpy as np
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _generate_error_bar_plot(mean_diff, std_diff, output_dir):
    """Generates and saves an error bar plot for x and y position differences."""
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
    plt.savefig(f"{output_dir}/error_bar_plot.png")
    plt.close(fig)
    logger.info(f"Error bar plot saved to {output_dir}/error_bar_plot.png")

def _generate_position_plot(plan_positions, log_positions, output_dir):
    """Generates and saves a 2D position comparison plot."""
    fig, ax = plt.subplots(figsize=(10, 10))

    # Keep track of labels to avoid duplicates in the legend
    plan_labeled = False
    log_labeled = False

    for layer_plan, layer_log in zip(plan_positions, log_positions):
        # Plot Plan data as a red solid line
        ax.plot(layer_plan[:, 0], layer_plan[:, 1], 'r-', linewidth=1, label='Plan' if not plan_labeled else "")
        plan_labeled = True

        # Sample and plot Log data as blue '+' markers
        # Sampling every 10th point as per the requirement
        sampled_log = layer_log[::10]
        ax.scatter(sampled_log[:, 0], sampled_log[:, 1], c='b', marker='+', s=10, label='Log' if not log_labeled else "")
        log_labeled = True

    ax.set_title('2D Position Comparison')
    ax.set_xlabel('X Position (mm)')
    ax.set_ylabel('Y Position (mm)')
    ax.legend()
    ax.grid(True)
    ax.set_aspect('equal', adjustable='box')
    plt.savefig(f"{output_dir}/position_comparison_plot.png")
    plt.close(fig)
    logger.info(f"Position comparison plot saved to {output_dir}/position_comparison_plot.png")


def generate_report(plan_data, log_data, output_dir):
    """
    Generates and saves analysis plots to the specified directory.

    Args:
        plan_data (dict): A dictionary containing data from the treatment plan.
                          Expected keys: 'mean_diff', 'std_diff', 'positions'.
        log_data (dict): A dictionary containing data from the machine logs.
                         Expected keys: 'positions'.
        output_dir (str): The directory where the plot images will be saved.
    """
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # 1. Generate and save the error bar plot
    if 'mean_diff' in plan_data and 'std_diff' in plan_data:
        _generate_error_bar_plot(plan_data['mean_diff'], plan_data['std_diff'], output_dir)
    else:
        logger.warning("Mean/Std difference data not available for error bar plot.")

    # 2. Generate and save the 2D position comparison plot
    if 'positions' in plan_data and 'positions' in log_data:
        _generate_position_plot(plan_data['positions'], log_data['positions'], output_dir)
    else:
        logger.warning("Position data not available for 2D position plot.")