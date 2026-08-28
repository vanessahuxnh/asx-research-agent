"""Safe, dependency-free SVG visualizations for agent tool calls."""

import json
import math
import os
import textwrap
from collections import defaultdict, deque
from datetime import datetime
from html import escape

from config import VISUALIZATION_OUTPUT_DIR


PALETTE = ["#6ee7b7", "#60a5fa", "#fbbf24", "#f472b6", "#a78bfa", "#fb7185", "#2dd4bf", "#fb923c"]
BG = "#12141a"
PANEL = "#181b23"
TEXT = "#e8e9ed"
MUTED = "#8b8fa3"
GRID = "#303441"


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must contain only numbers")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{field} cannot contain NaN or infinite values")
    return value


def _write_svg(svg, prefix):
    os.makedirs(VISUALIZATION_OUTPUT_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.abspath(os.path.join(VISUALIZATION_OUTPUT_DIR, f"{prefix}_{stamp}.svg"))
    with open(path, "w", encoding="utf-8") as output:
        output.write(svg)
    return path


def _fmt_value(value, value_format):
    if value_format == "percent":
        return f"{value * 100:.1f}%"
    if value_format == "currency":
        return f"${value:,.2f}"
    magnitude = abs(value)
    if magnitude >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if magnitude >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if magnitude >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _svg_shell(title, body, width, height, description):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{escape(title)}" viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px;height:auto;background:{BG};border-radius:12px">
  <title>{escape(title)}</title>
  <desc>{escape(description)}</desc>
  <rect width="100%" height="100%" rx="12" fill="{BG}"/>
  <text x="32" y="38" fill="{TEXT}" font-family="system-ui,sans-serif" font-size="20" font-weight="600">{escape(title)}</text>
  {body}
</svg>'''


def create_chart(title, chart_type, labels, series, x_axis_label="", y_axis_label="", value_format="number"):
    """Create a bar, line, area, scatter, or pie chart and save it as SVG."""
    title = str(title or "Chart")[:160]
    x_axis_label = str(x_axis_label or "")[:100]
    y_axis_label = str(y_axis_label or "")[:100]
    if chart_type not in {"bar", "line", "area", "scatter", "pie"}:
        raise ValueError("chart_type must be bar, line, area, scatter, or pie")
    if value_format not in {"number", "currency", "percent"}:
        raise ValueError("value_format must be number, currency, or percent")
    if not isinstance(labels, list) or not labels or len(labels) > 100:
        raise ValueError("labels must contain between 1 and 100 items")
    labels = [str(label)[:80] for label in labels]
    if not isinstance(series, list) or not series or len(series) > len(PALETTE):
        raise ValueError(f"series must contain between 1 and {len(PALETTE)} items")

    clean_series = []
    for index, item in enumerate(series):
        if not isinstance(item, dict):
            raise ValueError("each series must be an object")
        values = item.get("values")
        if not isinstance(values, list) or len(values) != len(labels):
            raise ValueError(f"series[{index}].values must have one value per label")
        clean = {
            "name": str(item.get("name") or f"Series {index + 1}")[:80],
            "values": [_number(value, f"series[{index}].values") for value in values],
        }
        if chart_type == "scatter":
            x_values = item.get("x_values")
            if not isinstance(x_values, list) or len(x_values) != len(labels):
                raise ValueError(f"series[{index}].x_values must have one value per label for scatter charts")
            clean["x_values"] = [_number(value, f"series[{index}].x_values") for value in x_values]
        clean_series.append(clean)

    if chart_type == "pie":
        if len(clean_series) != 1:
            raise ValueError("pie charts require exactly one series")
        if len(labels) > 10:
            raise ValueError("pie charts support no more than 10 categories")
        if any(value < 0 for value in clean_series[0]["values"]) or sum(clean_series[0]["values"]) <= 0:
            raise ValueError("pie chart values must be non-negative and total more than zero")
        body = _pie_chart(labels, clean_series[0], value_format)
        svg = _svg_shell(title, body, 800, 500, f"Pie chart with {len(labels)} categories")
    else:
        body = _cartesian_chart(
            chart_type, labels, clean_series, x_axis_label, y_axis_label, value_format
        )
        svg = _svg_shell(
            title, body, 900, 520,
            f"{chart_type.title()} chart with {len(clean_series)} series and {len(labels)} data points",
        )

    path = _write_svg(svg, f"chart_{chart_type}")
    return json.dumps({
        "visualization_path": path,
        "visualization_type": "chart",
        "chart_type": chart_type,
        "title": title,
        "series_count": len(clean_series),
        "point_count": len(labels),
    })


def _cartesian_chart(chart_type, labels, series, x_axis_label, y_axis_label, value_format):
    width, height = 900, 520
    left, right, top, bottom = 92, 38, 88, 78
    plot_w, plot_h = width - left - right, height - top - bottom
    all_y = [value for item in series for value in item["values"]]
    y_min, y_max = min(min(all_y), 0.0), max(max(all_y), 0.0)
    if y_min == y_max:
        padding = abs(y_min) * 0.1 or 1.0
        y_min -= padding
        y_max += padding
    y_span = y_max - y_min
    y_of = lambda value: top + (y_max - value) / y_span * plot_h

    parts = []
    for tick in range(6):
        value = y_min + y_span * tick / 5
        y = y_of(value)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" fill="{MUTED}" font-family="system-ui,sans-serif" font-size="11">{escape(_fmt_value(value, value_format))}</text>')

    zero_y = y_of(0)
    parts.append(f'<line x1="{left}" y1="{zero_y:.1f}" x2="{width-right}" y2="{zero_y:.1f}" stroke="{MUTED}" stroke-width="1.2"/>')

    if chart_type == "scatter":
        all_x = [value for item in series for value in item["x_values"]]
        x_min, x_max = min(all_x), max(all_x)
        if x_min == x_max:
            x_min -= 1
            x_max += 1
        x_span = x_max - x_min
        x_of = lambda value: left + (value - x_min) / x_span * plot_w
        for tick in range(6):
            value = x_min + x_span * tick / 5
            x = x_of(value)
            parts.append(f'<text x="{x:.1f}" y="{height-bottom+22}" text-anchor="middle" fill="{MUTED}" font-family="system-ui,sans-serif" font-size="11">{escape(_fmt_value(value, "number"))}</text>')
        for series_index, item in enumerate(series):
            color = PALETTE[series_index]
            for point_index, (x_value, y_value) in enumerate(zip(item["x_values"], item["values"])):
                parts.append(f'<circle cx="{x_of(x_value):.1f}" cy="{y_of(y_value):.1f}" r="5" fill="{color}"><title>{escape(labels[point_index])}: {_fmt_value(y_value, value_format)}</title></circle>')
    else:
        count = len(labels)
        step = plot_w / count
        centers = [left + step * (index + 0.5) for index in range(count)]
        label_stride = max(1, math.ceil(count / 12))
        for index, (label, x) in enumerate(zip(labels, centers)):
            if index % label_stride == 0:
                parts.append(f'<text x="{x:.1f}" y="{height-bottom+22}" text-anchor="middle" fill="{MUTED}" font-family="system-ui,sans-serif" font-size="11">{escape(label[:16])}</text>')

        if chart_type == "bar":
            group_w = step * 0.72
            bar_w = max(2, group_w / len(series))
            for series_index, item in enumerate(series):
                color = PALETTE[series_index]
                for point_index, value in enumerate(item["values"]):
                    x = centers[point_index] - group_w / 2 + series_index * bar_w
                    y = min(y_of(value), zero_y)
                    bar_h = max(1, abs(y_of(value) - zero_y))
                    parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(1, bar_w-2):.1f}" height="{bar_h:.1f}" rx="2" fill="{color}"><title>{escape(labels[point_index])} — {escape(item["name"])}: {_fmt_value(value, value_format)}</title></rect>')
        else:
            for series_index, item in enumerate(series):
                color = PALETTE[series_index]
                points = [(centers[index], y_of(value)) for index, value in enumerate(item["values"])]
                point_string = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
                if chart_type == "area":
                    area = f"{points[0][0]:.1f},{zero_y:.1f} {point_string} {points[-1][0]:.1f},{zero_y:.1f}"
                    parts.append(f'<polygon points="{area}" fill="{color}" opacity="0.18"/>')
                parts.append(f'<polyline points="{point_string}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
                for point_index, (x, y) in enumerate(points):
                    value = item["values"][point_index]
                    parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"><title>{escape(labels[point_index])} — {escape(item["name"])}: {_fmt_value(value, value_format)}</title></circle>')

    legend_x = width - right
    for index, item in enumerate(reversed(series)):
        actual_index = len(series) - index - 1
        label_width = min(150, 28 + len(item["name"]) * 7)
        legend_x -= label_width
        parts.append(f'<circle cx="{legend_x+7}" cy="64" r="5" fill="{PALETTE[actual_index]}"/><text x="{legend_x+18}" y="68" fill="{TEXT}" font-family="system-ui,sans-serif" font-size="12">{escape(item["name"][:20])}</text>')

    if x_axis_label:
        parts.append(f'<text x="{left+plot_w/2:.1f}" y="{height-18}" text-anchor="middle" fill="{MUTED}" font-family="system-ui,sans-serif" font-size="12">{escape(x_axis_label)}</text>')
    if y_axis_label:
        parts.append(f'<text x="20" y="{top+plot_h/2:.1f}" text-anchor="middle" transform="rotate(-90 20 {top+plot_h/2:.1f})" fill="{MUTED}" font-family="system-ui,sans-serif" font-size="12">{escape(y_axis_label)}</text>')
    return "".join(parts)


def _pie_chart(labels, series, value_format):
    values = series["values"]
    total = sum(values)
    cx, cy, radius = 270, 275, 155
    parts = []
    angle = -math.pi / 2
    for index, (label, value) in enumerate(zip(labels, values)):
        if value == 0:
            continue
        color = PALETTE[index % len(PALETTE)]
        if math.isclose(value, total):
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{color}" stroke="{BG}" stroke-width="2"><title>{escape(label)}: {_fmt_value(value, value_format)} (100.0%)</title></circle>')
            angle += 2 * math.pi
            continue
        next_angle = angle + 2 * math.pi * value / total
        x1, y1 = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
        x2, y2 = cx + radius * math.cos(next_angle), cy + radius * math.sin(next_angle)
        large = 1 if next_angle - angle > math.pi else 0
        path = f"M {cx} {cy} L {x1:.2f} {y1:.2f} A {radius} {radius} 0 {large} 1 {x2:.2f} {y2:.2f} Z"
        parts.append(f'<path d="{path}" fill="{color}" stroke="{BG}" stroke-width="2"><title>{escape(label)}: {_fmt_value(value, value_format)} ({value/total:.1%})</title></path>')
        angle = next_angle

    for index, (label, value) in enumerate(zip(labels, values)):
        y = 118 + index * 38
        color = PALETTE[index % len(PALETTE)]
        parts.append(f'<rect x="500" y="{y-11}" width="14" height="14" rx="3" fill="{color}"/><text x="524" y="{y}" fill="{TEXT}" font-family="system-ui,sans-serif" font-size="13">{escape(label[:24])}</text><text x="744" y="{y}" text-anchor="end" fill="{MUTED}" font-family="system-ui,sans-serif" font-size="12">{value/total:.1%}</text>')
    return "".join(parts)


def create_diagram(title, nodes, edges, direction="top_down"):
    """Create a simple flow/relationship diagram and save it as SVG."""
    title = str(title or "Diagram")[:160]
    if direction not in {"top_down", "left_right"}:
        raise ValueError("direction must be top_down or left_right")
    if not isinstance(nodes, list) or not nodes or len(nodes) > 30:
        raise ValueError("nodes must contain between 1 and 30 items")
    if not isinstance(edges, list) or len(edges) > 60:
        raise ValueError("edges must be a list with no more than 60 items")

    clean_nodes = []
    ids = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or not str(node.get("id", "")).strip():
            raise ValueError(f"nodes[{index}] requires a non-empty id")
        node_id = str(node["id"])[:80]
        if node_id in ids:
            raise ValueError(f"duplicate node id: {node_id}")
        ids.add(node_id)
        shape = node.get("shape", "rounded")
        if shape not in {"box", "rounded", "circle", "diamond"}:
            raise ValueError(f"unsupported node shape: {shape}")
        layer = node.get("layer")
        if layer is not None and (isinstance(layer, bool) or not isinstance(layer, int) or layer < 0 or layer > 20):
            raise ValueError("node layers must be integers from 0 to 20")
        clean_nodes.append({
            "id": node_id,
            "label": str(node.get("label") or node_id)[:120],
            "shape": shape,
            "group": str(node.get("group") or "default")[:80],
            "layer": layer,
        })

    clean_edges = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise ValueError(f"edges[{index}] must be an object")
        source, target = str(edge.get("from", "")), str(edge.get("to", ""))
        if source not in ids or target not in ids:
            raise ValueError(f"edges[{index}] references an unknown node")
        clean_edges.append({"from": source, "to": target, "label": str(edge.get("label") or "")[:80]})

    layers = _diagram_layers(clean_nodes, clean_edges)
    groups = list(dict.fromkeys(node["group"] for node in clean_nodes))
    group_colors = {group: PALETTE[index % len(PALETTE)] for index, group in enumerate(groups)}
    positions, width, height = _diagram_positions(layers, direction)
    body = _diagram_svg(clean_nodes, clean_edges, positions, group_colors, direction)
    svg = _svg_shell(title, body, width, height, f"Diagram with {len(clean_nodes)} nodes and {len(clean_edges)} connections")
    path = _write_svg(svg, "diagram")
    return json.dumps({
        "visualization_path": path,
        "visualization_type": "diagram",
        "title": title,
        "node_count": len(clean_nodes),
        "edge_count": len(clean_edges),
    })


def _diagram_layers(nodes, edges):
    explicit = any(node["layer"] is not None for node in nodes)
    if explicit:
        by_layer = defaultdict(list)
        for node in nodes:
            by_layer[node["layer"] or 0].append(node["id"])
        return [by_layer[key] for key in sorted(by_layer)]

    outgoing = defaultdict(list)
    indegree = {node["id"]: 0 for node in nodes}
    for edge in edges:
        outgoing[edge["from"]].append(edge["to"])
        indegree[edge["to"]] += 1
    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    levels = {node_id: 0 for node_id in queue}
    while queue:
        source = queue.popleft()
        for target in outgoing[source]:
            levels[target] = max(levels.get(target, 0), levels[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    for node in nodes:  # Cycles and disconnected cyclic components.
        levels.setdefault(node["id"], 0)
    by_layer = defaultdict(list)
    for node in nodes:
        by_layer[levels[node["id"]]].append(node["id"])
    return [by_layer[key] for key in sorted(by_layer)]


def _diagram_positions(layers, direction):
    max_items = max(len(layer) for layer in layers)
    if direction == "top_down":
        width = max(760, 80 + max_items * 220)
        height = max(300, 100 + len(layers) * 145)
        positions = {}
        for layer_index, layer in enumerate(layers):
            spacing = width / (len(layer) + 1)
            for item_index, node_id in enumerate(layer):
                positions[node_id] = (spacing * (item_index + 1), 100 + layer_index * 145)
    else:
        width = max(760, 130 + len(layers) * 230)
        height = max(320, 70 + max_items * 120)
        positions = {}
        for layer_index, layer in enumerate(layers):
            spacing = (height - 60) / (len(layer) + 1)
            for item_index, node_id in enumerate(layer):
                positions[node_id] = (120 + layer_index * 230, 60 + spacing * (item_index + 1))
    return positions, width, height


def _diagram_svg(nodes, edges, positions, group_colors, direction):
    parts = ['<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#8b8fa3"/></marker></defs>']
    for edge in edges:
        sx, sy = positions[edge["from"]]
        tx, ty = positions[edge["to"]]
        if direction == "top_down" and ty != sy:
            start, end = (sx, sy + 34), (tx, ty - 34)
        elif direction == "left_right" and tx != sx:
            start, end = (sx + 92, sy), (tx - 92, ty)
        else:
            start, end = (sx, sy + 34), (tx, ty - 34)
        parts.append(f'<line x1="{start[0]:.1f}" y1="{start[1]:.1f}" x2="{end[0]:.1f}" y2="{end[1]:.1f}" stroke="{MUTED}" stroke-width="1.6" marker-end="url(#arrow)"/>')
        if edge["label"]:
            mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
            label = escape(edge["label"])
            parts.append(f'<rect x="{mx-48:.1f}" y="{my-12:.1f}" width="96" height="20" rx="4" fill="{BG}"/><text x="{mx:.1f}" y="{my+3:.1f}" text-anchor="middle" fill="{MUTED}" font-family="system-ui,sans-serif" font-size="11">{label}</text>')

    for node in nodes:
        x, y = positions[node["id"]]
        color = group_colors[node["group"]]
        shape = node["shape"]
        if shape == "circle":
            parts.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="86" ry="38" fill="{PANEL}" stroke="{color}" stroke-width="2"/>')
        elif shape == "diamond":
            points = f"{x:.1f},{y-44:.1f} {x+96:.1f},{y:.1f} {x:.1f},{y+44:.1f} {x-96:.1f},{y:.1f}"
            parts.append(f'<polygon points="{points}" fill="{PANEL}" stroke="{color}" stroke-width="2"/>')
        else:
            radius = 10 if shape == "rounded" else 0
            parts.append(f'<rect x="{x-92:.1f}" y="{y-34:.1f}" width="184" height="68" rx="{radius}" fill="{PANEL}" stroke="{color}" stroke-width="2"/>')
        lines = textwrap.wrap(node["label"], width=24)[:2] or [node["id"]]
        first_y = y - (len(lines) - 1) * 9
        parts.append(f'<text x="{x:.1f}" y="{first_y:.1f}" text-anchor="middle" fill="{TEXT}" font-family="system-ui,sans-serif" font-size="13" font-weight="600">')
        for index, line in enumerate(lines):
            parts.append(f'<tspan x="{x:.1f}" dy="{0 if index == 0 else 18}">{escape(line)}</tspan>')
        parts.append('</text>')
    return "".join(parts)
