import matplotlib.pyplot as plt
import numpy as np

from src.report_constants import A4_FIGSIZE


def _gamma_percent(value):
    numeric = float(value)
    return numeric * 100.0 if numeric <= 1.0 else numeric


def _safe_grid(grid):
    if grid is None:
        return None
    array = np.asarray(grid, dtype=float)
    if array.ndim != 2 or array.size == 0:
        return None
    return array


def generate_point_gamma_visual_page(
    beam_name,
    layer_data,
    *,
    patient_id="",
    patient_name="",
):
    layer_batch = layer_data if isinstance(layer_data, list) else [layer_data]

    fig, axes = plt.subplots(4, 2, figsize=A4_FIGSIZE)
    fig.subplots_adjust(top=0.94, hspace=0.75, wspace=0.25)
    fig.suptitle(
        f"{beam_name} | Patient {patient_id} {patient_name}".strip(),
        fontsize=12,
        fontweight="bold",
    )

    for row_axes in axes:
        for ax in row_axes:
            ax.set_xticks([])
            ax.set_yticks([])

    for row_idx, current_layer in enumerate(layer_batch):
        layer_number = int(current_layer.get("layer_index", 0)) // 2 + 1
        results = current_layer.get("results", {})
        gamma_map = _safe_grid(results.get("gamma_map"))

        map_ax = axes[row_idx, 0]
        meta_ax = axes[row_idx, 1]

        map_ax.set_title(f"Layer {layer_number} | Point Gamma Map", fontsize=8)
        if gamma_map is None:
            map_ax.text(
                0.5,
                0.5,
                "No data",
                transform=map_ax.transAxes,
                ha="center",
                va="center",
                fontsize=9,
                color="#777777",
            )
            map_ax.set_facecolor("#f3f4f6")
        else:
            image = map_ax.imshow(
                gamma_map,
                origin="lower",
                cmap="magma",
                interpolation="nearest",
            )
            fig.colorbar(image, ax=map_ax, fraction=0.046, pad=0.04)

        meta_ax.set_title(f"Layer {layer_number} | Point Gamma Metrics", fontsize=8)
        meta_ax.axis("off")
        text_lines = [
            f"Pass rate: {float(_gamma_percent(results.get('pass_rate', 0.0))):.1f}%",
            f"Point gamma mean: {float(results.get('gamma_mean', 0.0)):.3f}",
            f"Point gamma max: {float(results.get('gamma_max', 0.0)):.3f}",
            f"Evaluated points: {int(results.get('evaluated_point_count', 0))}",
            f"Position error mean: {float(results.get('position_error_mean_mm', 0.0)):.3f} mm",
            f"Count error mean: {float(results.get('count_error_mean', 0.0)):.3g}",
        ]
        meta_ax.text(
            0.02,
            0.95,
            "\n".join(text_lines),
            ha="left",
            va="top",
            fontsize=8,
            family="monospace",
        )

    for row_idx in range(len(layer_batch), 4):
        for ax in axes[row_idx]:
            ax.axis("off")

    return fig
