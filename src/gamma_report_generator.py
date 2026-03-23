import logging
import os

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from src.gamma_report_layout import (
    generate_gamma_summary_page as _generate_gamma_summary_page,
    generate_gamma_visual_page as _generate_gamma_visual_page,
)


logger = logging.getLogger(__name__)


def _batched_layers(layers, batch_size=4):
    for start_idx in range(0, len(layers), batch_size):
        yield layers[start_idx:start_idx + batch_size]


def generate_gamma_report(
    report_data,
    output_dir,
    *,
    report_name=None,
    analysis_config=None,
):
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{report_name}.pdf" if report_name else "analysis_report.pdf"
    pdf_path = os.path.join(output_dir, filename)
    patient_id = report_data.get("_patient_id", "")
    patient_name = report_data.get("_patient_name", "")

    with PdfPages(pdf_path) as pdf:
        for beam_name, beam_data in report_data.items():
            if beam_name.startswith("_"):
                continue
            if not beam_data.get("layers"):
                logger.warning("No gamma layers for beam '%s'. Skipping.", beam_name)
                continue

            summary_fig = _generate_gamma_summary_page(
                beam_name,
                beam_data,
                patient_id=patient_id,
                patient_name=patient_name,
                analysis_config=analysis_config,
            )
            pdf.savefig(summary_fig)
            plt.close(summary_fig)

            for layer_data in _batched_layers(beam_data.get("layers", []), batch_size=4):
                visual_fig = _generate_gamma_visual_page(
                    beam_name,
                    layer_data,
                    patient_id=patient_id,
                    patient_name=patient_name,
                )
                pdf.savefig(visual_fig)
                plt.close(visual_fig)

    logger.info("Gamma analysis report saved to %s", pdf_path)


__all__ = [
    "generate_gamma_report",
    "_generate_gamma_summary_page",
    "_generate_gamma_visual_page",
]
