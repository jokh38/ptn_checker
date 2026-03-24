import os
import shutil
import tempfile
import unittest

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")

from src.point_gamma_report_generator import (
    generate_point_gamma_report,
    _generate_point_gamma_summary_page,
    _generate_point_gamma_visual_page,
)


class TestPointGammaReportGenerator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.test_dir, "point_gamma_report_output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.report_data = {
            "Beam 1": {
                "beam_number": 1,
                "layers": [
                    {
                        "layer_index": 0,
                        "results": {
                            "pass_rate": 1.0,
                            "gamma_mean": 0.0,
                            "gamma_max": 0.0,
                            "evaluated_point_count": 4,
                            "gamma_map": np.array([[0.0, 0.2], [0.1, 0.3]]),
                            "position_error_mean_mm": 0.15,
                            "count_error_mean": 0.01,
                        },
                    }
                ],
            }
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_generate_point_gamma_summary_page_returns_figure(self):
        fig = _generate_point_gamma_summary_page(
            "Beam 1",
            self.report_data["Beam 1"],
            patient_id="12345",
            patient_name="Test^Point",
            analysis_config={
                "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
                "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
                "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            },
        )
        self.assertIsInstance(fig, plt.Figure)
        rendered_text = " ".join(
            text.get_text()
            for ax in fig.axes
            for text in ax.texts
        )
        self.assertIn("Beam 1", rendered_text)
        self.assertIn("PASS", rendered_text)
        self.assertIn("Point Gamma Summary", rendered_text)
        plt.close(fig)

    def test_generate_point_gamma_visual_page_renders_gamma_maps(self):
        layer_batch = [
            {
                "layer_index": idx * 2,
                "results": {
                    **self.report_data["Beam 1"]["layers"][0]["results"],
                    "gamma_mean": float(idx),
                    "position_error_mean_mm": 0.1 + idx * 0.01,
                    "count_error_mean": 0.01 + idx * 0.001,
                },
            }
            for idx in range(4)
        ]
        fig = _generate_point_gamma_visual_page(
            "Beam 1",
            layer_batch,
            patient_id="12345",
            patient_name="Test^Point",
        )
        self.assertIsInstance(fig, plt.Figure)
        self.assertGreaterEqual(len(fig.axes), 8)
        axis_text = " ".join(
            " ".join(text.get_text() for text in ax.texts)
            for ax in fig.axes
        )
        axis_titles = " ".join(ax.get_title() for ax in fig.axes)
        combined_labels = f"{axis_text} {axis_titles}"
        self.assertIn("Point Gamma Map", combined_labels)
        self.assertIn("Point Gamma Metrics", combined_labels)
        self.assertIn("Layer 1", combined_labels)
        self.assertIn("Layer 4", combined_labels)
        plt.close(fig)

    def test_generate_point_gamma_report_writes_pdf(self):
        pdf_path = os.path.join(self.output_dir, "point_gamma_report.pdf")
        generate_point_gamma_report(
            self.report_data,
            self.output_dir,
            report_name="point_gamma_report",
            analysis_config={
                "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
                "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
                "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
            },
        )
        self.assertTrue(os.path.exists(pdf_path))

    def test_generate_point_gamma_report_batches_four_layers_per_visual_page(self):
        report_data = {
            "Beam 1": {
                "beam_number": 1,
                "layers": [
                    {
                        "layer_index": idx * 2,
                        "results": self.report_data["Beam 1"]["layers"][0]["results"],
                    }
                    for idx in range(5)
                ],
            }
        }

        with unittest.mock.patch(
            "src.point_gamma_report_generator._generate_point_gamma_visual_page"
        ) as visual_mock:
            visual_mock.return_value = plt.figure()
            generate_point_gamma_report(
                report_data,
                self.output_dir,
                report_name="point_gamma_report",
                analysis_config={
                    "GAMMA_FLUENCE_PERCENT_THRESHOLD": 5.0,
                    "GAMMA_DISTANCE_MM_THRESHOLD": 2.0,
                    "GAMMA_LOWER_PERCENT_FLUENCE_CUTOFF": 10.0,
                },
            )

        self.assertEqual(2, visual_mock.call_count)


if __name__ == "__main__":
    unittest.main()
