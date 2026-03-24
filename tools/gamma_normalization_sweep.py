import argparse
import csv
import json
import os
import sys
from statistics import mean

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import main
from src.analysis_context import load_plan_and_machine_config, parse_ptn_with_optional_mu_correction
from src.config_loader import parse_yaml_config
from src.gamma_workflow import calculate_gamma_for_layer


def generate_linear_micro_factors(*, start: float, step: float, count: int) -> list[float]:
    return [round(start + step * idx, 12) for idx in range(count)]


def summarize_factor_result(factor: float, layer_rows: list[dict]) -> dict:
    valid_rows = [row for row in layer_rows if "gamma_mean" in row]
    return {
        "factor": factor,
        "layer_count": len(valid_rows),
        "layer_gamma_means": [row["gamma_mean"] for row in valid_rows],
        "layer_pass_rates": [row["pass_rate"] for row in valid_rows],
        "avg_gamma_mean": mean(row["gamma_mean"] for row in valid_rows) if valid_rows else float("inf"),
        "avg_pass_rate": mean(row["pass_rate"] for row in valid_rows) if valid_rows else 0.0,
    }


def select_optimal_factor(factor_rows: list[dict]) -> dict:
    summarized = []
    for row in factor_rows:
        if "avg_gamma_mean" not in row:
            if "layer_gamma_means" in row:
                row = {
                    "factor": row["factor"],
                    "layer_count": len(row.get("layer_gamma_means", [])),
                    "layer_gamma_means": row.get("layer_gamma_means", []),
                    "layer_pass_rates": row.get("layer_pass_rates", []),
                    "avg_gamma_mean": mean(row.get("layer_gamma_means", [float("inf")])),
                    "avg_pass_rate": mean(row.get("layer_pass_rates", [0.0])),
                }
            else:
                row = summarize_factor_result(row["factor"], row.get("layer_rows", []))
        summarized.append(row)
    return min(summarized, key=lambda row: (row["avg_gamma_mean"], -row["avg_pass_rate"]))


def _collect_layer_pairs(log_dir, dcm_file, app_config_path: str):
    app_config = parse_yaml_config(app_config_path)
    plan_data_raw, config = load_plan_and_machine_config(dcm_file, zero_dose_config=app_config)
    analysis_config = {**config, **app_config}
    analysis_config["ANALYSIS_MODE"] = "gamma"

    delivery_groups = main.collect_ptn_delivery_groups(log_dir)
    treatment_beams = {
        beam_number: beam_data for beam_number, beam_data in plan_data_raw["beams"].items()
    }
    matched_groups = main.match_delivery_groups_to_beams(treatment_beams, delivery_groups)

    pairs = []
    for beam_number in sorted(treatment_beams):
        matched_group = matched_groups.get(beam_number)
        if matched_group is None:
            continue
        ptn_iter = iter(matched_group["ptn_files"])
        beam_data = treatment_beams[beam_number]
        for layer_index, layer_data in beam_data.get("layers", {}).items():
            try:
                ptn_file = next(ptn_iter)
            except StopIteration:
                break
            log_data = parse_ptn_with_optional_mu_correction(
                ptn_file,
                config,
                matched_group["planrange_lookup"],
            )
            pairs.append(
                {
                    "beam_number": beam_number,
                    "beam_name": beam_data.get("name", f"Beam {beam_number}"),
                    "layer_index": int(layer_index),
                    "layer_number": int(layer_index) // 2 + 1,
                    "ptn_file": os.path.basename(ptn_file),
                    "plan_layer": layer_data,
                    "log_data": log_data,
                    "analysis_config": analysis_config,
                }
            )
    return pairs


def run_sweep(log_dir: str, dcm_file: str, *, start: float, step: float, count: int, app_config_path: str) -> dict:
    factors = generate_linear_micro_factors(start=start, step=step, count=count)
    layer_pairs = _collect_layer_pairs(log_dir, dcm_file, app_config_path)
    factor_summaries = []

    for factor in factors:
        layer_rows = []
        for pair in layer_pairs:
            cfg = dict(pair["analysis_config"])
            cfg["GAMMA_NORMALIZATION_FACTOR"] = factor
            result = calculate_gamma_for_layer(pair["plan_layer"], pair["log_data"], cfg)
            if "error" in result:
                continue
            layer_rows.append(
                {
                    "beam_number": pair["beam_number"],
                    "beam_name": pair["beam_name"],
                    "layer_index": pair["layer_index"],
                    "layer_number": pair["layer_number"],
                    "ptn_file": pair["ptn_file"],
                    "gamma_mean": float(result["gamma_mean"]),
                    "pass_rate": float(result["pass_rate"]),
                }
            )
        summary = summarize_factor_result(factor, layer_rows)
        summary["layer_rows"] = layer_rows
        factor_summaries.append(summary)

    best = select_optimal_factor(factor_summaries)
    return {"factors": factor_summaries, "best": best}


def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log_dir", required=True)
    parser.add_argument("--dcm_file", required=True)
    parser.add_argument("--start", type=float, default=1e-6)
    parser.add_argument("--step", type=float, default=1e-6)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--csv_out", default="")
    args = parser.parse_args()

    result = run_sweep(
        args.log_dir,
        args.dcm_file,
        start=args.start,
        step=args.step,
        count=args.count,
        app_config_path=args.config,
    )

    if args.csv_out:
        os.makedirs(os.path.dirname(args.csv_out) or ".", exist_ok=True)
        with open(args.csv_out, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["factor", "layer_count", "avg_gamma_mean", "avg_pass_rate"],
            )
            writer.writeheader()
            for row in result["factors"]:
                writer.writerow(
                    {
                        "factor": row["factor"],
                        "layer_count": row["layer_count"],
                        "avg_gamma_mean": row["avg_gamma_mean"],
                        "avg_pass_rate": row["avg_pass_rate"],
                    }
                )

    print(json.dumps(result["best"], indent=2))


if __name__ == "__main__":
    main_cli()
