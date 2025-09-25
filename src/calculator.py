import numpy as np
from scipy.optimize import curve_fit


def gaussian(x, amplitude, mean, stddev):
    """Gaussian function for curve fitting."""
    return amplitude * np.exp(-((x - mean) / stddev)**2 / 2)


def calculate_differences_for_layer(plan_layer, log_data):
    """
    Calculates the differences between planned and actual data for a single layer.

    Args:
        plan_layer: A dictionary containing the plan data for a single layer.
        log_data: Parsed data from a PTN log file for the corresponding layer.

    Returns:
        A dictionary containing the analysis results for the layer.
    """
    results = {}
    plan_mu = plan_layer['cumulative_mu']
    plan_x = plan_layer['positions'][:, 0]
    plan_y = plan_layer['positions'][:, 1]

    log_mu = log_data['mu']
    log_x = log_data['x']
    log_y = log_data['y']

    # 1. 초기 데이터 확인
    print("\n--- [DEBUG] Initial Data Check ---")
    print(f"Plan X (first 5): {plan_x[:5]}")
    print(f"Plan Y (first 5): {plan_y[:5]}")
    print(f"Log X (first 5): {log_x[:5]}")
    print(f"Log Y (first 5): {log_y[:5]}")

    if len(plan_mu) == 0 or len(log_mu) == 0:
        return {'error': 'Empty data arrays'}

    if plan_mu[-1] > 0:
        plan_mu_norm = plan_mu / plan_mu[-1]
    else:
        plan_mu_norm = plan_mu

    if log_mu[-1] > 0:
        log_mu_norm = log_mu / log_mu[-1]
    else:
        log_mu_norm = log_mu

    interp_plan_x = np.interp(log_mu_norm, plan_mu_norm, plan_x)
    interp_plan_y = np.interp(log_mu_norm, plan_mu_norm, plan_y)

    # 2. 보간 후 데이터 확인
    print("--- [DEBUG] Interpolated Data Check ---")
    print(f"Interpolated Plan X (first 5): {interp_plan_x[:5]}")
    print(f"Interpolated Plan Y (first 5): {interp_plan_y[:5]}")

    diff_x = interp_plan_x - log_x
    diff_y = interp_plan_y - log_y

    # 3. 최종 차이 값 확인
    print("--- [DEBUG] Final Difference Check ---")
    print(f"Difference X (first 5): {diff_x[:5]}")
    print(f"Difference Y (first 5): {diff_y[:5]}")

    results['diff_x'] = diff_x
    results['diff_y'] = diff_y

    bins = np.arange(-5, 5.01, 0.01)
    hist_x, _ = np.histogram(diff_x, bins=bins, density=True)
    hist_y, _ = np.histogram(diff_y, bins=bins, density=True)
    bin_centers = (bins[:-1] + bins[1:]) / 2

    try:
        if (np.sum(hist_x) > 0 and not np.isinf(np.sum(hist_x)) and not
                np.isnan(np.sum(hist_x))):
            params_x, _ = curve_fit(
                gaussian, bin_centers, hist_x, p0=[1, 0, 1])
        else:
            params_x = [0, 0, 0]
        if (np.sum(hist_y) > 0 and not np.isinf(np.sum(hist_y)) and not
                np.isnan(np.sum(hist_y))):
            params_y, _ = curve_fit(
                gaussian, bin_centers, hist_y, p0=[1, 0, 1])
        else:
            params_y = [0, 0, 0]
        results['hist_fit_x'] = {
            'amplitude': params_x[0],
            'mean': params_x[1],
            'stddev': params_x[2]
        }
        results['hist_fit_y'] = {
            'amplitude': params_y[0],
            'mean': params_y[1],
            'stddev': params_y[2]
        }
    except RuntimeError:
        results['hist_fit_x'] = {'amplitude': 0, 'mean': 0, 'stddev': 0}
        results['hist_fit_y'] = {'amplitude': 0, 'mean': 0, 'stddev': 0}

    # Add missing keys expected by report generator
    results['plan_positions'] = np.column_stack((interp_plan_x, interp_plan_y))
    results['log_positions'] = np.column_stack((log_x, log_y))
    results['mean_diff_x'] = np.mean(diff_x)
    results['mean_diff_y'] = np.mean(diff_y)
    results['std_diff_x'] = np.std(diff_x)
    results['std_diff_y'] = np.std(diff_y)

    return results
