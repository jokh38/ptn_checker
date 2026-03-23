from datetime import date as _date

import matplotlib.pyplot as plt
import numpy as np

from src.report_constants import A4_FIGSIZE


def _gamma_percent(value):
    numeric = float(value)
    return numeric * 100.0 if numeric <= 1.0 else numeric


def _gamma_beam_verdict(pass_rate_percent):
    if pass_rate_percent >= 95.0:
        return "PASS", "#2ecc71"
    if pass_rate_percent >= 80.0:
        return "CONDITIONAL", "#e67e22"
    return "FAIL", "#e74c3c"


def _collect_gamma_layer_rows(layers_data):
    rows = []
    weighted_pass_total = 0.0
    evaluated_point_total = 0
    for layer in layers_data:
        results = layer.get("results", {})
        layer_number = int(layer.get("layer_index", 0)) // 2 + 1
        pass_rate_percent = _gamma_percent(results.get("pass_rate", 0.0))
        evaluated_point_count = int(results.get("evaluated_point_count", 0))
        weighted_pass_total += pass_rate_percent * evaluated_point_count
        evaluated_point_total += evaluated_point_count
        rows.append(
            [
                f"L{layer_number}",
                f"{pass_rate_percent:.1f}",
                f"{float(results.get('gamma_mean', 0.0)):.3f}",
                f"{float(results.get('gamma_max', 0.0)):.3f}",
                f"{int(results.get('evaluated_point_count', 0))}",
                f"{float(results.get('unmatched_delivered_weight', 0.0)):.3f}",
            ]
        )
    return rows, weighted_pass_total, evaluated_point_total


def _safe_grid(grid):
    if grid is None:
        return None
    array = np.asarray(grid, dtype=float)
    if array.ndim != 2 or array.size == 0:
        return None
    return array


def generate_gamma_summary_page(
    beam_name,
    beam_data,
    *,
    patient_id="",
    patient_name="",
    analysis_config=None,
):
    layers_data = beam_data.get("layers", [])
    layer_rows, weighted_pass_total, evaluated_point_total = _collect_gamma_layer_rows(layers_data)
    beam_pass_rate = (
        float(weighted_pass_total / evaluated_point_total)
        if evaluated_point_total > 0
        else 0.0
    )
    displayed_beam_pass_rate = float(round(beam_pass_rate))
    verdict, verdict_color = _gamma_beam_verdict(beam_pass_rate)

    fig = plt.figure(figsize=A4_FIGSIZE)

    header_ax = fig.add_axes([0.06, 0.88, 0.88, 0.08])
    header_ax.axis("off")
    header_ax.text(0.5, 0.72, beam_name, ha="center", va="center", fontsize=16, fontweight="bold")
    header_ax.text(
        0.98,
        0.72,
        verdict,
        ha="right",
        va="center",
        fontsize=10,
        fontweight="bold",
        color="white",
        bbox=dict(boxstyle="round,pad=0.3", facecolor=verdict_color, edgecolor="none"),
    )
    header_ax.text(
        0.5,
        0.22,
        (
            f"Patient ID: {patient_id} | Name: {patient_name} | "
            f"Date: {_date.today().isoformat()} | Layers: {len(layers_data)} | "
            f"Pass rate: {displayed_beam_pass_rate:.1f}"
        ),
        ha="center",
        va="center",
        fontsize=8,
        color="#555555",
    )

    info_ax = fig.add_axes([0.06, 0.74, 0.40, 0.10])
    info_ax.axis("off")
    cfg = analysis_config or {}
    info_ax.text(0.0, 0.95, "Gamma Summary", ha="left", va="top", fontsize=9, fontweight="bold")
    info_ax.text(
        0.0,
        0.68,
        (
            f"Thresholds: {cfg.get('GAMMA_FLUENCE_PERCENT_THRESHOLD', 0):.1f}% / "
            f"{cfg.get('GAMMA_DISTANCE_MM_THRESHOLD', 0):.1f} mm"
        ),
        ha="left",
        va="top",
        fontsize=7,
    )
    if layers_data:
        sample_results = layers_data[0].get("results", {})
        info_ax.text(
            0.0,
            0.43,
            f"Normalization: {sample_results.get('normalization_mode', 'unknown')}",
            ha="left",
            va="top",
            fontsize=7,
        )
        info_ax.text(
            0.0,
            0.18,
            (
                "PlanRange MU correction: "
                f"{'yes' if sample_results.get('used_planrange_mu_correction') else 'no'}"
            ),
            ha="left",
            va="top",
            fontsize=7,
        )

    table_ax = fig.add_axes([0.06, 0.08, 0.88, 0.62])
    table_ax.axis("off")
    if layer_rows:
        table = table_ax.table(
            cellText=layer_rows,
            colLabels=[
                "Layer",
                "Pass Rate (%)",
                "Gamma Mean",
                "Gamma Max",
                "Points",
                "Unmatched Wt",
            ],
            loc="upper center",
            cellLoc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(7)
        table.scale(1.0, 1.3)
        for idx in range(6):
            table[0, idx].set_facecolor("#34495e")
            table[0, idx].set_text_props(color="white", fontweight="bold")
    else:
        table_ax.text(0.5, 0.5, "No gamma layer data", ha="center", va="center", fontsize=12)

    return fig


def generate_gamma_visual_page(
    beam_name,
    layer_data,
    *,
    patient_id="",
    patient_name="",
):
    layer_batch = layer_data if isinstance(layer_data, list) else [layer_data]

    fig, axes = plt.subplots(4, 3, figsize=A4_FIGSIZE)
    fig.subplots_adjust(top=0.94, hspace=0.85, wspace=0.35)
    fig.suptitle(
        f"{beam_name} | Patient {patient_id} {patient_name}".strip(),
        fontsize=12,
        fontweight="bold",
    )

    panel_specs = (
        ("Plan Fluence", "plan_grid", "viridis"),
        ("Log Fluence", "log_grid", "viridis"),
        ("Gamma Map", "gamma_map", "magma"),
    )

    for row_axes in axes:
        for ax in row_axes:
            ax.set_xticks([])
            ax.set_yticks([])

    for row_idx, current_layer in enumerate(layer_batch):
        layer_number = int(current_layer.get("layer_index", 0)) // 2 + 1
        results = current_layer.get("results", {})
        for col_idx, (title, grid_key, cmap) in enumerate(panel_specs):
            ax = axes[row_idx, col_idx]
            display_title = f"Layer {layer_number} | {title}"
            ax.set_title(display_title, fontsize=8)
            safe_grid = _safe_grid(results.get(grid_key))
            if safe_grid is None:
                ax.text(
                    0.5,
                    0.5,
                    "No data",
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=9,
                    color="#777777",
                )
                ax.set_facecolor("#f3f4f6")
                continue
            image = ax.imshow(safe_grid, origin="lower", cmap=cmap)
            fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    for row_idx in range(len(layer_batch), 4):
        for ax in axes[row_idx]:
            ax.axis("off")

    return fig
