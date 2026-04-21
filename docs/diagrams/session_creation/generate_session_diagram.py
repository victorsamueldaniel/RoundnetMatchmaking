"""Generate SESSION_CREATION_DIAGRAM.md from registry data."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = SCRIPT_DIR / "session_diagram_registry.json"
DEFAULT_OUTPUT = SCRIPT_DIR / "SESSION_CREATION_DIAGRAM.md"


def _sanitize_identifier(raw: str, prefix: str = "n") -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", raw)
    if not sanitized:
        sanitized = prefix
    if sanitized[0].isdigit():
        sanitized = f"{prefix}_{sanitized}"
    return sanitized


def _escape_mermaid(text: str) -> str:
    return text.replace('"', "'")


def _escape_table_cell(value: Any) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def _source_link(path: str, output_dir: Path, line: int | None = None) -> str:
    normalized = path.replace("\\", "/")
    target_abs = ROOT / normalized
    target = Path(os.path.relpath(target_abs, output_dir)).as_posix()
    if line is not None:
        return f"[{normalized}:{line}]({target}#L{line})"
    return f"[{normalized}]({target})"


def _load_registry(path: Path) -> dict[str, Any]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    required_keys = [
        "meta",
        "layers",
        "nodes",
        "edges",
        "entities",
        "entity_relationships",
        "parameter_rows",
        "artifacts",
    ]
    missing = [key for key in required_keys if key not in registry]
    if missing:
        missing_txt = ", ".join(missing)
        raise ValueError(f"Registry file is missing required keys: {missing_txt}")
    return registry


def _render_call_flow(registry: dict[str, Any]) -> str:
    layers = registry["layers"]
    nodes = registry["nodes"]
    edges = registry["edges"]

    nodes_by_layer: dict[str, list[dict[str, Any]]] = {
        layer["id"]: [] for layer in layers
    }
    orphan_nodes: list[dict[str, Any]] = []

    for node in nodes:
        layer_id = node["layer"]
        if layer_id in nodes_by_layer:
            nodes_by_layer[layer_id].append(node)
        else:
            orphan_nodes.append(node)

    lines = ["```mermaid", "flowchart LR"]

    for layer in layers:
        layer_id = layer["id"]
        layer_var = _sanitize_identifier(f"layer_{layer_id}", prefix="layer")
        layer_label = _escape_mermaid(layer["label"])
        lines.append(f'  subgraph {layer_var}["{layer_label}"]')
        for node in nodes_by_layer[layer_id]:
            node_var = _sanitize_identifier(node["id"])
            node_label = _escape_mermaid(node["label"])
            lines.append(f'    {node_var}["{node_label}"]')
        lines.append("  end")

    if orphan_nodes:
        lines.append('  subgraph layer_orphan["Unmapped Layer"]')
        for node in orphan_nodes:
            node_var = _sanitize_identifier(node["id"])
            node_label = _escape_mermaid(node["label"])
            lines.append(f'    {node_var}["{node_label}"]')
        lines.append("  end")

    for edge in edges:
        src = _sanitize_identifier(edge["from"])
        dst = _sanitize_identifier(edge["to"])
        label = edge.get("label")
        if label:
            lines.append(f"  {src} -->|{_escape_mermaid(label)}| {dst}")
        else:
            lines.append(f"  {src} --> {dst}")

    lines.append("```")
    return "\n".join(lines)


def _render_nodes_table(registry: dict[str, Any], output_dir: Path) -> str:
    layers = {layer["id"]: layer["label"] for layer in registry["layers"]}
    rows = [
        "| Node | Layer | Location | Key Parameters | Notes |",
        "|---|---|---|---|---|",
    ]
    for node in registry["nodes"]:
        location = _source_link(node["file"], output_dir, node.get("line"))
        params = ", ".join(node.get("parameters", [])) or "-"
        notes = node.get("notes", "-")
        rows.append(
            "| "
            + " | ".join(
                [
                    _escape_table_cell(node["label"]),
                    _escape_table_cell(layers.get(node["layer"], node["layer"])),
                    _escape_table_cell(location),
                    _escape_table_cell(params),
                    _escape_table_cell(notes),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _render_er_diagram(registry: dict[str, Any]) -> str:
    entities = registry["entities"]
    relationships = registry["entity_relationships"]
    entity_names = {
        entity["id"]: _sanitize_identifier(entity["id"], prefix="e").upper()
        for entity in entities
    }

    lines = ["```mermaid", "erDiagram"]
    for relation in relationships:
        left = entity_names[relation["from"]]
        right = entity_names[relation["to"]]
        connector = relation.get("connector", "||--o{")
        label = _sanitize_identifier(relation.get("label", "related_to")).lower()
        lines.append(f"  {left} {connector} {right} : {label}")

    for entity in entities:
        entity_name = entity_names[entity["id"]]
        lines.append(f"  {entity_name} {{")
        attributes = entity.get("attributes", [])
        if attributes:
            for attribute in attributes:
                attr_type = _sanitize_identifier(
                    attribute.get("type", "string")
                ).lower()
                attr_name = _sanitize_identifier(attribute.get("name", "field")).lower()
                lines.append(f"    {attr_type} {attr_name}")
        else:
            lines.append("    string id")
        lines.append("  }")

    lines.append("```")
    return "\n".join(lines)


def _render_entities_table(registry: dict[str, Any], output_dir: Path) -> str:
    rows = [
        "| Entity | Kind | Location | Attributes |",
        "|---|---|---|---|",
    ]
    for entity in registry["entities"]:
        location = _source_link(entity["file"], output_dir, entity.get("line"))
        attributes = ", ".join(
            f"{item.get('type', 'string')} {item.get('name', 'field')}"
            for item in entity.get("attributes", [])
        )
        rows.append(
            "| "
            + " | ".join(
                [
                    _escape_table_cell(entity["label"]),
                    _escape_table_cell(entity.get("kind", "entity")),
                    _escape_table_cell(location),
                    _escape_table_cell(attributes or "-"),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _render_parameter_tables(registry: dict[str, Any]) -> str:
    grouped_rows: dict[str, list[dict[str, Any]]] = {}
    group_order: list[str] = []

    for row in registry["parameter_rows"]:
        group = row.get("group", "Other")
        if group not in grouped_rows:
            grouped_rows[group] = []
            group_order.append(group)
        grouped_rows[group].append(row)

    sections: list[str] = []
    for group in group_order:
        sections.append(f"### {group}")
        sections.append("| Parameter | Source | Passed To | Default | Type | Notes |")
        sections.append("|---|---|---|---|---|---|")
        for row in grouped_rows[group]:
            sections.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(row.get("parameter", "-")),
                        _escape_table_cell(row.get("source", "-")),
                        _escape_table_cell(row.get("passed_to", "-")),
                        _escape_table_cell(row.get("default", "-")),
                        _escape_table_cell(row.get("type", "-")),
                        _escape_table_cell(row.get("notes", "-")),
                    ]
                )
                + " |"
            )
        sections.append("")

    return "\n".join(sections).strip()


def _render_artifacts_table(registry: dict[str, Any]) -> str:
    rows = [
        "| Artifact | Path Pattern | Generated By | Notes |",
        "|---|---|---|---|",
    ]
    for artifact in registry["artifacts"]:
        rows.append(
            "| "
            + " | ".join(
                [
                    _escape_table_cell(artifact.get("name", "-")),
                    _escape_table_cell(artifact.get("path_pattern", "-")),
                    _escape_table_cell(artifact.get("generated_by", "-")),
                    _escape_table_cell(artifact.get("notes", "-")),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _render_maintenance_steps(registry: dict[str, Any]) -> str:
    steps = registry.get("maintenance", {}).get("how_to_add_feature", [])
    if not steps:
        return "1. Edit registry entries.\n2. Regenerate docs."
    return "\n".join(f"{idx}. {step}" for idx, step in enumerate(steps, start=1))


def _generate_markdown(registry: dict[str, Any], output_path: Path) -> str:
    title = registry["meta"].get("title", "Session Creation Diagram")
    description = registry["meta"].get("description", "")
    source_of_truth = registry["meta"].get(
        "source_of_truth",
        "docs/diagrams/session_creation/session_diagram_registry.json",
    )
    output_dir = output_path.parent

    sections = [
        f"# {title}",
        "",
        "> This document is generated. Do not edit by hand.",
        f"> Source of truth: {source_of_truth}",
        "",
        description,
        "",
        "## Call Flow",
        _render_call_flow(registry),
        "",
        "## Function Nodes",
        _render_nodes_table(registry, output_dir),
        "",
        "## Data Model",
        _render_er_diagram(registry),
        "",
        "## Entities",
        _render_entities_table(registry, output_dir),
        "",
        "## Parameter Matrix",
        _render_parameter_tables(registry),
        "",
        "## Session Artifacts",
        _render_artifacts_table(registry),
        "",
        "## How To Add a Feature",
        _render_maintenance_steps(registry),
        "",
    ]

    return "\n".join(sections).strip() + "\n"


def _print_diff(current: str, expected: str, output_path: Path) -> None:
    diff = difflib.unified_diff(
        current.splitlines(),
        expected.splitlines(),
        fromfile=str(output_path),
        tofile=f"generated:{output_path}",
        lineterm="",
    )
    max_lines = 200
    for idx, line in enumerate(diff):
        if idx >= max_lines:
            print("... diff truncated ...")
            break
        print(line)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate SESSION_CREATION_DIAGRAM.md from JSON registry"
    )
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="Path to session diagram registry JSON",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path to generated markdown output",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if output file is not in sync with registry",
    )
    args = parser.parse_args()

    registry_path = Path(args.registry).resolve()
    output_path = Path(args.output).resolve()

    registry = _load_registry(registry_path)
    generated = _generate_markdown(registry, output_path)

    if args.check:
        if not output_path.exists():
            print(f"Output file is missing: {output_path}")
            return 1
        current = output_path.read_text(encoding="utf-8")
        if current != generated:
            print("Session diagram doc is out of date.")
            _print_diff(current, generated, output_path)
            return 1
        print("Session diagram doc is up to date.")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generated, encoding="utf-8")
    print(f"Generated session diagram doc at: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
