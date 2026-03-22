from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from .._converter_helpers import _json_default
from ..manifest import EpisodeManifest


def report_path_for_dataset(dataset_path: str | Path) -> Path:
    path = Path(dataset_path)
    return path.with_name(f"{path.stem}.report.md")


def _format_block(title: str, payload: Any) -> list[str]:
    return [
        f"## {title}",
        "```json",
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default),
        "```",
        "",
    ]


def build_conversion_report(
    *,
    manifest: EpisodeManifest,
    preview_rows: Sequence[dict[str, Any]] | None = None,
) -> str:
    schema = manifest.conversion.schema_spec or {}
    source = manifest.source.model_dump()
    dataset = manifest.dataset.model_dump()
    conversion = manifest.conversion.model_dump()

    lines: list[str] = ["# conversion report", ""]
    lines.extend(
        [
            f"- episode id: {manifest.episode_id}",
            f"- schema: {schema.get('name', 'unknown')} v{schema.get('version', 'unknown')}",
            f"- dataset path: {dataset['path']}",
            f"- output format: {dataset['format']}",
            f"- rows written: {dataset['rows_written']}",
            f"- file size bytes: {dataset['file_size_bytes']}",
        ]
    )
    if conversion.get("row_strategy") is not None:
        lines.append(f"- row strategy: {conversion['row_strategy'].get('kind', 'unknown')}")

    if dataset.get("split_name") is not None:
        lines.append(f"- split: {dataset['split_name']}")
    if dataset.get("shard_index") is not None:
        lines.append(f"- shard: {dataset['shard_index']} of {dataset['num_shards']}")
    if dataset.get("output_filename") is not None:
        lines.append(f"- output filename: {dataset['output_filename']}")
    if manifest.conversion.dropped_rows is not None:
        lines.append(f"- dropped rows: {manifest.conversion.dropped_rows}")
    lines.append("")

    lines.extend(_format_block("Source Metadata", source))
    lines.extend(_format_block("Temporal Metadata", manifest.temporal.model_dump()))
    lines.extend(_format_block("Output Config", conversion["output"]))

    if conversion.get("row_strategy") is not None:
        lines.extend(_format_block("Row Strategy", conversion["row_strategy"]))
    if conversion.get("resample") is not None:
        lines.extend(_format_block("Resample Config", conversion["resample"]))
    if conversion.get("schema_spec") is not None:
        lines.extend(_format_block("Resolved Schema", conversion["schema_spec"]))
    if conversion.get("features"):
        lines.extend(_format_block("Resolved Features", conversion["features"]))
    if conversion.get("labels_spec") is not None:
        lines.extend(_format_block("Label Config", conversion["labels_spec"]))
    if conversion.get("draft_origin") is not None:
        lines.extend(_format_block("Draft Origin", conversion["draft_origin"]))
    if conversion.get("split") is not None:
        lines.extend(_format_block("Split Config", conversion["split"]))
    if conversion.get("validation") is not None:
        lines.extend(_format_block("Validation Config", conversion["validation"]))
    if conversion.get("preflight") is not None:
        lines.extend(_format_block("Preflight Summary", conversion["preflight"]))
    if conversion.get("mapping_requested"):
        lines.extend(_format_block("Requested Mapping", conversion["mapping_requested"]))
    if conversion.get("mapping_resolved"):
        lines.extend(_format_block("Resolved Mapping", conversion["mapping_resolved"]))

    if conversion.get("split_counts"):
        lines.extend(_format_block("Split Counts", conversion["split_counts"]))
    if conversion.get("missing_feature_counts"):
        lines.extend(_format_block("Missing Feature Counts", conversion["missing_feature_counts"]))
    if conversion.get("missing_topic_counts"):
        lines.extend(_format_block("Missing Topic Counts", conversion["missing_topic_counts"]))
    if conversion.get("missing_feature_rates"):
        lines.extend(_format_block("Missing Feature Rates", conversion["missing_feature_rates"]))
    if conversion.get("missing_topic_rates"):
        lines.extend(_format_block("Missing Topic Rates", conversion["missing_topic_rates"]))

    if manifest.robot_context is not None:
        lines.extend(_format_block("Robot Context", manifest.robot_context))

    if preview_rows:
        lines.extend(_format_block("Preview", list(preview_rows)))

    return "\n".join(lines).rstrip() + "\n"


def write_conversion_report(
    *,
    manifest: EpisodeManifest,
    dataset_path: str | Path,
    preview_rows: Sequence[dict[str, Any]] | None = None,
) -> Path:
    report_path = report_path_for_dataset(dataset_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        build_conversion_report(manifest=manifest, preview_rows=preview_rows),
        encoding="utf-8",
    )
    return report_path
