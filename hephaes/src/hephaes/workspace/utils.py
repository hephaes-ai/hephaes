from __future__ import annotations

import json
import mimetypes
from datetime import UTC, datetime
from pathlib import Path

from ..conversion.spec_io import (
    ConversionSpecDocument,
    build_conversion_spec_document,
    load_conversion_spec_document,
)
from ..models import ConversionSpec
from .errors import InvalidAssetPathError

SUPPORTED_ASSET_FILE_TYPES = frozenset({"bag", "mcap"})


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_root(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _normalize_asset_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _infer_asset_file_type(path: Path) -> str:
    suffix = path.suffix.strip().lower()
    if suffix.startswith("."):
        suffix = suffix[1:]
    return suffix or "unknown"


def _inspect_asset_path(path: str | Path) -> tuple[Path, str, int]:
    normalized = _normalize_asset_path(path)
    if not normalized.exists():
        raise InvalidAssetPathError(f"asset path does not exist: {normalized}")
    if not normalized.is_file():
        raise InvalidAssetPathError(f"asset path is not a file: {normalized}")

    file_type = _infer_asset_file_type(normalized)
    if file_type not in SUPPORTED_ASSET_FILE_TYPES:
        supported_types = ", ".join(sorted(SUPPORTED_ASSET_FILE_TYPES))
        raise InvalidAssetPathError(
            f"unsupported asset type: {normalized.name} (supported: {supported_types})"
        )

    return normalized, file_type, normalized.stat().st_size


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _write_text_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def _load_conversion_document_input(
    spec_document: ConversionSpecDocument | ConversionSpec | dict | str | Path,
) -> ConversionSpecDocument:
    if isinstance(spec_document, ConversionSpec):
        return build_conversion_spec_document(spec_document)
    return load_conversion_spec_document(spec_document)


def _build_config_document_relative_path(config_id: str) -> str:
    return f"{config_id}.json"


def _build_config_revision_relative_path(revision_id: str) -> str:
    return f"revisions/{revision_id}.json"


def _build_draft_revision_relative_path(draft_id: str) -> str:
    return f"drafts/{draft_id}.json"


def _infer_output_format_and_role(path: Path) -> tuple[str, str]:
    name = path.name.lower()
    if name.endswith(".manifest.json"):
        return "json", "manifest"
    if name.endswith(".report.md"):
        return "md", "report"
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return "parquet", "dataset"
    if suffix == ".tfrecord":
        return "tfrecord", "dataset"
    if suffix == ".jsonl":
        return "jsonl", "sidecar"
    if suffix == ".json":
        return "json", "sidecar"
    return suffix.lstrip(".") or "unknown", "sidecar"


def _infer_media_type(path: Path, format_name: str) -> str | None:
    if format_name == "parquet":
        return "application/x-parquet"
    if format_name == "tfrecord":
        return "application/octet-stream"
    if format_name == "json":
        return "application/json"
    if format_name == "jsonl":
        return "application/x-ndjson"
    return mimetypes.guess_type(path.name)[0]


def _load_json_file(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _summarize_output_metadata(path: Path, *, format_name: str, role: str) -> dict:
    metadata: dict = {}
    if role == "manifest":
        payload = _load_json_file(path)
        if payload is not None:
            metadata["manifest"] = payload
        return metadata

    manifest_path = path.with_suffix(".manifest.json")
    if manifest_path.exists():
        manifest_payload = _load_json_file(manifest_path)
        if manifest_payload is not None:
            metadata["manifest"] = manifest_payload
    return metadata


def _relative_output_path(output_root: Path, artifact_path: Path) -> str:
    try:
        return str(artifact_path.relative_to(output_root))
    except ValueError:
        return artifact_path.name
