from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                              Paragraph, Spacer, Image, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
import matplotlib.pyplot as plt
import numpy as np
import io

from src.calculator import gaussian


def generate_report(plan_data, all_analysis_results, output_path):
    """
    Generates a PDF report from the analysis results.
    """
    doc = SimpleDocTemplate(output_path)
    styles = getSampleStyleSheet()
    story = []
    title = Paragraph("Spot Position Check Report", styles['h1'])
    story.append(title)
    story.append(Spacer(1, 0.2*inch))
    patient_name = plan_data.get('patient_name', 'N/A')
    patient_id = plan_data.get('patient_id', 'N/A')
    p_info = f"Patient Name: {patient_name}<br/>Patient ID: {patient_id}"
    patient_info = Paragraph(p_info, styles['Normal'])
    story.append(patient_info)
    story.append(Spacer(1, 0.2*inch))

    summary_data = [
        ["Beam", "Layer", "Axis", "Offset (mm)", "Std Dev (mm)"],
    ]
    for beam_name, beam_results in all_analysis_results.items():
        for layer_index, layer_results in beam_results.items():
            fit_x = layer_results.get('hist_fit_x', {})
            fit_y = layer_results.get('hist_fit_y', {})
            summary_data.append([beam_name, layer_index, "X",
                                 f"{fit_x.get('mean', 0):.3f}",
                                 f"{fit_x.get('stddev', 0):.3f}"])
            summary_data.append(["", "", "Y", f"{fit_y.get('mean', 0):.3f}",
                                 f"{fit_y.get('stddev', 0):.3f}"])

    summary_table = Table(summary_data)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(summary_table)

    for beam_name, beam_results in all_analysis_results.items():
        for layer_index, layer_results in beam_results.items():
            story.append(PageBreak())
            layer_title = f"Beam: {beam_name}, Layer: {layer_index}"
            story.append(Paragraph(layer_title, styles['h2']))
            story.append(Spacer(1, 0.2*inch))

            diff_x = layer_results.get('diff_x', np.array([]))
            diff_y = layer_results.get('diff_y', np.array([]))

            fig = plt.figure(figsize=(6, 4))
            try:
                plt.plot(diff_x, label="X-difference")
                plt.plot(diff_y, label="Y-difference")
                plt.title("Position Differences (Plan - Log)")
                plt.xlabel("Spot Index")
                plt.ylabel("Difference (mm)")
                plt.legend()
                plt.grid(True)

                img_buffer = io.BytesIO()
                plt.savefig(img_buffer, format='png')
                img_buffer.seek(0)
                story.append(Image(img_buffer, width=5*inch, height=3*inch))
            finally:
                plt.close(fig)

            story.append(Spacer(1, 0.2*inch))

            bins = np.arange(-5, 5.01, 0.01)
            bin_centers = (bins[:-1] + bins[1:]) / 2

            fig = plt.figure(figsize=(6, 4))
            try:
                plt.hist(diff_x, bins=bins, density=True, label='X-diff Histogram')
                if 'hist_fit_x' in layer_results:
                    fit_params = layer_results['hist_fit_x']
                    if fit_params.get('amplitude', 0) > 0:
                        plt.plot(bin_centers, gaussian(bin_centers, **fit_params),
                                 'r-', label='Gaussian Fit')
                plt.title("X-Difference Histogram")
                plt.xlabel("Difference (mm)")
                plt.ylabel("Probability Density")
                plt.legend()
                plt.grid(True)

                img_buffer = io.BytesIO()
                plt.savefig(img_buffer, format='png')
                img_buffer.seek(0)
                story.append(Image(img_buffer, width=5*inch, height=3*inch))
            finally:
                plt.close(fig)

            story.append(Spacer(1, 0.2*inch))

            fig = plt.figure(figsize=(6, 4))
            try:
                plt.hist(diff_y, bins=bins, density=True, label='Y-diff Histogram')
                if 'hist_fit_y' in layer_results:
                    fit_params = layer_results['hist_fit_y']
                    if fit_params.get('amplitude', 0) > 0:
                        plt.plot(bin_centers, gaussian(bin_centers, **fit_params),
                                 'r-', label='Gaussian Fit')
                plt.title("Y-Difference Histogram")
                plt.xlabel("Difference (mm)")
                plt.ylabel("Probability Density")
                plt.legend()
                plt.grid(True)

                img_buffer = io.BytesIO()
                plt.savefig(img_buffer, format='png')
                img_buffer.seek(0)
                story.append(Image(img_buffer, width=5*inch, height=3*inch))
            finally:
                plt.close(fig)

    doc.build(story)
