import csv
import os
import re

import numpy as np

from src.report_generator import _layer_passes, _metric_value, _spot_pass_summary


CSV_FIELDNAMES = [
    "patient_id",
    "patient_name",
    "beam_name",
    "beam_number",
    "layer_index_raw",
    "layer_number",
    "report_mode_used",
    "filtered_stats_available",
    "filtered_stats_fallback_to_raw",
    "layer_pass",
    "mean_diff_x_mm",
    "mean_diff_y_mm",
    "std_diff_x_mm",
    "std_diff_y_mm",
    "rmse_x_mm",
    "rmse_y_mm",
    "max_abs_diff_x_mm",
    "max_abs_diff_y_mm",
    "p95_abs_diff_x_mm",
    "p95_abs_diff_y_mm",
    "time_overlap_fraction",
    "settling_status",
    "settling_samples_count",
    "num_total_samples",
    "num_included_samples",
    "num_filtered_samples",
    "filtered_sample_fraction",
    "filtered_mu_fraction_estimate",
    "passed_spots",
    "total_spots",
    "spot_pass_rate_percent",
]


def _sanitize_filename(value):
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return sanitized or "beam"


def _metric_row(results, report_mode):
    return {
        "mean_diff_x_mm": _metric_value(results, "mean_diff_x", report_mode),
        "mean_diff_y_mm": _metric_value(results, "mean_diff_y", report_mode),
        "std_diff_x_mm": _metric_value(results, "std_diff_x", report_mode),
        "std_diff_y_mm": _metric_value(results, "std_diff_y", report_mode),
        "rmse_x_mm": _metric_value(results, "rmse_x", report_mode),
        "rmse_y_mm": _metric_value(results, "rmse_y", report_mode),
        "max_abs_diff_x_mm": _metric_value(results, "max_abs_diff_x", report_mode),
        "max_abs_diff_y_mm": _metric_value(results, "max_abs_diff_y", report_mode),
        "p95_abs_diff_x_mm": _metric_value(results, "p95_abs_diff_x", report_mode),
        "p95_abs_diff_y_mm": _metric_value(results, "p95_abs_diff_y", report_mode),
    }


def _build_layer_row(patient_id, patient_name, beam_name, beam_number, layer, report_mode):
    results = layer.get("results", {})
    layer_index = int(layer.get("layer_index", 0))
    passed_spots, total_spots = _spot_pass_summary(results, report_mode=report_mode)
    total_samples = len(np.asarray(results.get("diff_x", [])))

    if report_mode == "raw":
        num_included_samples = max(total_samples - int(results.get("settling_samples_count", 0)), 0)
        num_filtered_samples = 0
    else:
        num_included_samples = int(results.get("num_included_samples", 0))
        num_filtered_samples = int(results.get("num_filtered_samples", 0))

    return {
        "patient_id": patient_id,
        "patient_name": patient_name,
        "beam_name": beam_name,
        "beam_number": beam_number,
        "layer_index_raw": layer_index,
        "layer_number": layer_index // 2 + 1,
        "report_mode_used": report_mode,
        "filtered_stats_available": any(
            key.startswith("filtered_") for key in results
        ),
        "filtered_stats_fallback_to_raw": bool(
            results.get("filtered_stats_fallback_to_raw", False)
        ),
        "layer_pass": _layer_passes(results, report_mode=report_mode),
        **_metric_row(results, report_mode),
        "time_overlap_fraction": results.get("time_overlap_fraction"),
        "settling_status": results.get("settling_status", ""),
        "settling_samples_count": int(results.get("settling_samples_count", 0)),
        "num_total_samples": total_samples,
        "num_included_samples": num_included_samples,
        "num_filtered_samples": num_filtered_samples,
        "filtered_sample_fraction": results.get("filtered_sample_fraction"),
        "filtered_mu_fraction_estimate": results.get("filtered_mu_fraction_estimate"),
        "passed_spots": passed_spots,
        "total_spots": total_spots,
        "spot_pass_rate_percent": (
            (passed_spots / total_spots) * 100.0 if total_spots else 0.0
        ),
    }


def export_report_csv(report_data, output_dir, report_mode="raw"):
    os.makedirs(output_dir, exist_ok=True)
    patient_id = report_data.get("_patient_id", "")
    patient_name = report_data.get("_patient_name", "")
    written_files = []

    for beam_name, beam_data in report_data.items():
        if beam_name.startswith("_"):
            continue

        layers = beam_data.get("layers", [])
        if not layers:
            continue

        filename = f"{_sanitize_filename(beam_name)}_report_layers.csv"
        csv_path = os.path.join(output_dir, filename)
        rows = [
            _build_layer_row(
                patient_id,
                patient_name,
                beam_name,
                beam_data.get("beam_number", ""),
                layer,
                report_mode,
            )
            for layer in layers
        ]

        with open(csv_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

        written_files.append(csv_path)

    return written_files
