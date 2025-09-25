import numpy as np

def calculate_differences_for_layer(plan_layer, log_data):
    """
    Calculates the differences between planned and actual data for a single layer,
    including mean and standard deviation of the differences.

    Args:
        plan_layer: A dictionary containing the plan data for a single layer.
        log_data: Parsed data from a PTN log file for the corresponding layer.

    Returns:
        A dictionary containing the analysis results for the layer, including
        mean differences, standard deviations, and original positions.
    """
    results = {}
    plan_mu = plan_layer['cumulative_mu']
    plan_x = plan_layer['positions'][:, 0]
    plan_y = plan_layer['positions'][:, 1]

    log_mu = log_data['mu']
    log_x = log_data['x']
    log_y = log_data['y']

    if len(plan_mu) == 0 or len(log_mu) == 0:
        return {'error': 'Empty data arrays'}

    # Normalize MU values to create a common axis for interpolation
    plan_mu_norm = plan_mu / plan_mu[-1] if plan_mu[-1] > 0 else plan_mu
    log_mu_norm = log_mu / log_mu[-1] if log_mu[-1] > 0 else log_mu

    # Interpolate plan positions to match the log MU timestamps
    interp_plan_x = np.interp(log_mu_norm, plan_mu_norm, plan_x)
    interp_plan_y = np.interp(log_mu_norm, plan_mu_norm, plan_y)

    # Calculate the difference in mm
    diff_x = interp_plan_x - log_x
    diff_y = interp_plan_y - log_y

    # Calculate mean and standard deviation of the differences
    results['mean_diff_x'] = np.mean(diff_x)
    results['std_diff_x'] = np.std(diff_x)
    results['mean_diff_y'] = np.mean(diff_y)
    results['std_diff_y'] = np.std(diff_y)

    # Pass through the original positions for plotting
    results['plan_positions'] = plan_layer['positions']
    results['log_positions'] = np.column_stack((log_x, log_y))

    return results