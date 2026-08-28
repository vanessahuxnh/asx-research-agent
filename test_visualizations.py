import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import patch

import server
import visualizations


class VisualizationTests(unittest.TestCase):
    def test_bar_chart_is_saved_and_escapes_labels(self):
        with tempfile.TemporaryDirectory() as output_dir, patch.object(
            visualizations, "VISUALIZATION_OUTPUT_DIR", output_dir
        ):
            result = json.loads(visualizations.create_chart(
                title="Yield <comparison>",
                chart_type="bar",
                labels=["BHP", "RIO"],
                series=[{"name": "Dividend yield", "values": [0.052, 0.061]}],
                y_axis_label="Yield",
                value_format="percent",
            ))
            self.assertTrue(os.path.isfile(result["visualization_path"]))
            with open(result["visualization_path"], encoding="utf-8") as source:
                svg = source.read()
            self.assertIn("Yield &lt;comparison&gt;", svg)
            self.assertIn("5.2%", svg)
            self.assertNotIn("<comparison>", svg)

    def test_scatter_requires_x_values(self):
        with self.assertRaisesRegex(ValueError, "x_values"):
            visualizations.create_chart(
                title="Risk and return",
                chart_type="scatter",
                labels=["BHP"],
                series=[{"name": "Stocks", "values": [0.12]}],
            )

    def test_each_chart_type_produces_valid_svg(self):
        with tempfile.TemporaryDirectory() as output_dir, patch.object(
            visualizations, "VISUALIZATION_OUTPUT_DIR", output_dir
        ):
            cases = {
                "bar": {"labels": ["A", "B"], "series": [{"name": "S", "values": [1, -2]}]},
                "line": {"labels": ["A", "B"], "series": [{"name": "S", "values": [1, 2]}]},
                "area": {"labels": ["A", "B"], "series": [{"name": "S", "values": [1, 2]}]},
                "scatter": {"labels": ["A", "B"], "series": [{"name": "S", "x_values": [3, 4], "values": [1, 2]}]},
                "pie": {"labels": ["Only category"], "series": [{"name": "S", "values": [1]}]},
            }
            for chart_type, data in cases.items():
                with self.subTest(chart_type=chart_type):
                    result = json.loads(visualizations.create_chart(
                        title=f"{chart_type} chart", chart_type=chart_type, **data
                    ))
                    ET.parse(result["visualization_path"])
                    if chart_type == "pie":
                        with open(result["visualization_path"], encoding="utf-8") as source:
                            self.assertIn("100.0%", source.read())

    def test_diagram_is_saved_and_escapes_content(self):
        with tempfile.TemporaryDirectory() as output_dir, patch.object(
            visualizations, "VISUALIZATION_OUTPUT_DIR", output_dir
        ):
            result = json.loads(visualizations.create_diagram(
                title="Research flow",
                nodes=[
                    {"id": "fetch", "label": "Fetch <data>", "layer": 0},
                    {"id": "analyse", "label": "Analyse", "shape": "diamond", "layer": 1},
                ],
                edges=[{"from": "fetch", "to": "analyse", "label": "then"}],
            ))
            self.assertTrue(os.path.isfile(result["visualization_path"]))
            with open(result["visualization_path"], encoding="utf-8") as source:
                svg = source.read()
            self.assertIn("Fetch &lt;data&gt;", svg)
            self.assertNotIn("Fetch <data>", svg)

    def test_each_native_plot_type_produces_valid_svg(self):
        with tempfile.TemporaryDirectory() as output_dir, patch.object(
            visualizations, "VISUALIZATION_OUTPUT_DIR", output_dir
        ):
            cases = {
                "line": [{"name": "Trend", "x_values": [1, 2, 3], "values": [2, 4, 8]}],
                "scatter": [{"name": "Risk/return", "x_values": [0.8, 1.1], "values": [0.05, 0.09]}],
                "histogram": [{"name": "Returns", "values": [-0.02, -0.01, 0, 0.01, 0.04]}],
                "box": [
                    {"name": "Portfolio A", "values": [1, 2, 3, 4, 5]},
                    {"name": "Portfolio B", "values": [2, 4, 6, 8, 10]},
                ],
            }
            for plot_type, datasets in cases.items():
                with self.subTest(plot_type=plot_type):
                    result = json.loads(visualizations.create_plot(
                        title=f"{plot_type} plot",
                        plot_type=plot_type,
                        datasets=datasets,
                        bins=5,
                    ))
                    self.assertEqual(result["visualization_type"], "plot")
                    ET.parse(result["visualization_path"])

    def test_native_plot_validates_histogram_bins(self):
        with self.assertRaisesRegex(ValueError, "bins"):
            visualizations.create_plot(
                title="Bad histogram",
                plot_type="histogram",
                datasets=[{"name": "Values", "values": [1, 2, 3]}],
                bins=1,
            )

    def test_diagram_rejects_unknown_edge_node(self):
        with self.assertRaisesRegex(ValueError, "unknown node"):
            visualizations.create_diagram(
                title="Broken",
                nodes=[{"id": "known", "label": "Known"}],
                edges=[{"from": "known", "to": "missing"}],
            )

    def test_server_streams_generated_visualization_inline(self):
        tool_use = SimpleNamespace(
            type="tool_use",
            name="create_plot",
            id="tool-1",
            input={
                "title": "Inline plot",
                "plot_type": "histogram",
                "datasets": [{"name": "Returns", "values": [-0.01, 0, 0.02]}],
            },
        )
        responses = iter([
            SimpleNamespace(content=[tool_use], stop_reason="tool_use"),
            SimpleNamespace(content=[SimpleNamespace(type="text", text="Done")], stop_reason="end_turn"),
        ])
        fake_client = SimpleNamespace(
            messages=SimpleNamespace(create=lambda **_kwargs: next(responses))
        )
        with tempfile.TemporaryDirectory() as output_dir, patch.object(
            visualizations, "VISUALIZATION_OUTPUT_DIR", output_dir
        ), patch.object(
            server, "VISUALIZATION_OUTPUT_DIR", output_dir
        ), patch.object(
            server.anthropic, "Anthropic", return_value=fake_client
        ):
            events = "".join(server.stream_agent("Make a chart"))
        self.assertIn('"type": "visualization"', events)
        self.assertIn('<svg xmlns=\\"http://www.w3.org/2000/svg\\"', events)
        self.assertIn("Done\\n\\n## Sources", events)
        self.assertIn("No external sources were used", events)


if __name__ == "__main__":
    unittest.main()
