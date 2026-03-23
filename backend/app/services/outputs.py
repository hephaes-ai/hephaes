"""Service helpers for first-class conversion output artifacts."""

from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Conversion, OutputArtifact, utc_now

try:
    import pyarrow.parquet as pq
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    pq = None  # type: ignore[assignment]


class OutputArtifactServiceError(Exception):
    """Base exception for output artifact service failures."""


class OutputArtifactNotFoundError(OutputArtifactServiceError):
    """Raised when an output artifact id is unknown."""


class OutputArtifactContentUnavailableError(OutputArtifactServiceError):
    """Raised when an output artifact file cannot be served."""


@dataclass(frozen=True)
class OutputListFilters:
    """Normalized filters for listing output artifacts."""

    search: str | None = None
    format: str | None = None
    role: str | None = None
    asset_id: str | None = None
    conversion_id: str | None = None
    availability: str | None = None
    limit: int = 100
    offset: int = 0


def _candidate_output_paths(conversion: Conversion) -> list[Path]:
    paths: list[Path] = []

    for raw_path in conversion.output_files_json or []:
        dataset_path = Path(raw_path)
        if dataset_path not in paths:
            paths.append(dataset_path)

        manifest_path = dataset_path.with_suffix(".manifest.json")
        if manifest_path.exists() and manifest_path not in paths:
            paths.append(manifest_path)

        report_path = dataset_path.with_name(f"{dataset_path.stem}.report.md")
        if report_path.exists() and report_path not in paths:
            paths.append(report_path)

    return paths


def _relative_output_path(conversion: Conversion, artifact_path: Path) -> str:
    if conversion.output_path is None:
        return artifact_path.name

    output_dir = Path(conversion.output_path)
    try:
        return str(artifact_path.relative_to(output_dir))
    except ValueError:
        return artifact_path.name


def _infer_format_and_role(artifact_path: Path) -> tuple[str, str]:
    name = artifact_path.name.lower()

    if name.endswith(".manifest.json"):
        return "json", "manifest"
    if name.endswith(".report.md"):
        return "md", "report"
    if artifact_path.suffix.lower() == ".parquet":
        return "parquet", "dataset"
    if artifact_path.suffix.lower() == ".tfrecord":
        return "tfrecord", "dataset"
    if artifact_path.suffix.lower() == ".jsonl":
        return "jsonl", "sidecar"
    if artifact_path.suffix.lower() == ".json":
        return "json", "sidecar"

    normalized_suffix = artifact_path.suffix.lower().lstrip(".")
    return normalized_suffix or "unknown", "sidecar"


def _infer_media_type(artifact_path: Path, format_name: str) -> str | None:
    if format_name == "parquet":
        return "application/x-parquet"
    if format_name == "tfrecord":
        return "application/octet-stream"
    if format_name == "json":
        return "application/json"
    if format_name == "jsonl":
        return "application/x-ndjson"
    return mimetypes.guess_type(artifact_path.name)[0]


def _load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _summarize_manifest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    dataset = payload.get("dataset")
    source = payload.get("source")
    temporal = payload.get("temporal")
    conversion = payload.get("conversion")

    summary: dict[str, Any] = {
        "manifest_version": payload.get("manifest_version"),
        "episode_id": payload.get("episode_id"),
    }

    if isinstance(dataset, dict):
        summary["dataset"] = {
            "format": dataset.get("format"),
            "rows_written": dataset.get("rows_written"),
            "field_names": dataset.get("field_names"),
            "file_size_bytes": dataset.get("file_size_bytes"),
        }
    if isinstance(source, dict):
        summary["source"] = {
            "file_path": source.get("file_path"),
            "ros_version": source.get("ros_version"),
            "storage_format": source.get("storage_format"),
        }
    if isinstance(temporal, dict):
        summary["temporal"] = {
            "duration_seconds": temporal.get("duration_seconds"),
            "message_count": temporal.get("message_count"),
            "start_time_iso": temporal.get("start_time_iso"),
            "end_time_iso": temporal.get("end_time_iso"),
        }

    if isinstance(conversion, dict):
        payload_representation = conversion.get("payload_representation")
        if isinstance(payload_representation, dict):
            summary["payload_representation"] = {
                "image_payload_contract": payload_representation.get("image_payload_contract"),
                "payload_encoding": payload_representation.get("payload_encoding"),
                "null_encoding": payload_representation.get("null_encoding"),
            }

    return summary


def _inspect_parquet(path: Path) -> dict[str, Any]:
    if pq is None:
        return {}

    try:
        parquet_file = pq.ParquetFile(str(path))
    except Exception:
        return {}

    return {
        "schema_fields": list(parquet_file.schema.names),
        "row_group_count": parquet_file.num_row_groups,
    }


def _build_metadata_summary(
    artifact_path: Path,
    *,
    format_name: str,
    role: str,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    if role == "manifest":
        payload = _load_json_file(artifact_path)
        if payload is not None:
            metadata["manifest"] = _summarize_manifest_payload(payload)
        return metadata

    manifest_path = artifact_path.with_suffix(".manifest.json")
    if manifest_path.exists():
        payload = _load_json_file(manifest_path)
        if payload is not None:
            metadata["manifest"] = _summarize_manifest_payload(payload)

    if format_name == "parquet":
        parquet_summary = _inspect_parquet(artifact_path)
        if parquet_summary:
            metadata["parquet"] = parquet_summary

    return metadata


def _build_output_artifact_payload(conversion: Conversion, artifact_path: Path) -> dict[str, Any]:
    relative_path = _relative_output_path(conversion, artifact_path)
    format_name, role = _infer_format_and_role(artifact_path)

    if not artifact_path.exists():
        availability_status = "missing"
        size_bytes = 0
        metadata = {}
    elif not artifact_path.is_file():
        availability_status = "invalid"
        size_bytes = 0
        metadata = {}
    else:
        availability_status = "ready"
        size_bytes = artifact_path.stat().st_size
        metadata = _build_metadata_summary(artifact_path, format_name=format_name, role=role)

    return {
        "job_id": conversion.job_id,
        "source_asset_ids_json": list(conversion.source_asset_ids_json or []),
        "relative_path": relative_path,
        "file_name": artifact_path.name,
        "format": format_name,
        "role": role,
        "media_type": _infer_media_type(artifact_path, format_name),
        "size_bytes": size_bytes,
        "availability_status": availability_status,
        "metadata_json": metadata,
    }


def sync_output_artifacts_for_conversion(
    session: Session,
    conversion: Conversion,
    *,
    commit: bool = True,
) -> list[OutputArtifact]:
    """Create or update output artifact rows for one conversion."""
    candidate_paths = _candidate_output_paths(conversion)
    existing_by_relative_path = {
        artifact.relative_path: artifact
        for artifact in session.scalars(
            select(OutputArtifact).where(OutputArtifact.conversion_id == conversion.id)
        ).all()
    }

    synced_artifacts: list[OutputArtifact] = []

    for artifact_path in candidate_paths:
        payload = _build_output_artifact_payload(conversion, artifact_path)
        relative_path = str(payload["relative_path"])
        artifact = existing_by_relative_path.get(relative_path)

        if artifact is None:
            artifact = OutputArtifact(
                conversion_id=conversion.id,
                **payload,
            )
            session.add(artifact)
        else:
            artifact.job_id = str(payload["job_id"])
            artifact.source_asset_ids_json = list(payload["source_asset_ids_json"])
            artifact.file_name = str(payload["file_name"])
            artifact.format = str(payload["format"])
            artifact.role = str(payload["role"])
            artifact.media_type = payload["media_type"]  # type: ignore[assignment]
            artifact.size_bytes = int(payload["size_bytes"])
            artifact.availability_status = str(payload["availability_status"])
            artifact.metadata_json = dict(payload["metadata_json"])
            artifact.updated_at = utc_now()

        synced_artifacts.append(artifact)

    if commit:
        session.commit()
        return synced_artifacts

    session.flush()
    return synced_artifacts


def backfill_output_artifacts(session: Session) -> None:
    """Ensure succeeded conversions have registered output artifact rows."""
    conversions = list(
        session.scalars(
            select(Conversion).where(Conversion.status == "succeeded").order_by(Conversion.created_at.asc())
        ).all()
    )

    if not conversions:
        return

    any_changes = False
    for conversion in conversions:
        candidate_paths = _candidate_output_paths(conversion)
        if not candidate_paths:
            continue

        sync_output_artifacts_for_conversion(session, conversion, commit=False)
        any_changes = True

    if any_changes:
        session.commit()


def list_output_artifacts(session: Session, filters: OutputListFilters | None = None) -> list[OutputArtifact]:
    backfill_output_artifacts(session)

    resolved_filters = filters or OutputListFilters()
    statement = (
        select(OutputArtifact)
        .options(
            selectinload(OutputArtifact.conversion),
            selectinload(OutputArtifact.output_actions),
        )
        .order_by(OutputArtifact.created_at.desc(), OutputArtifact.id.desc())
    )
    artifacts = list(session.scalars(statement).all())

    def matches(artifact: OutputArtifact) -> bool:
        if resolved_filters.conversion_id is not None and artifact.conversion_id != resolved_filters.conversion_id:
            return False
        if resolved_filters.asset_id is not None and resolved_filters.asset_id not in (artifact.source_asset_ids_json or []):
            return False
        if resolved_filters.format is not None and artifact.format.lower() != resolved_filters.format:
            return False
        if resolved_filters.role is not None and artifact.role.lower() != resolved_filters.role:
            return False
        if (
            resolved_filters.availability is not None
            and artifact.availability_status.lower() != resolved_filters.availability
        ):
            return False
        if resolved_filters.search is not None:
            haystack = " ".join(
                [
                    artifact.file_name,
                    artifact.relative_path,
                    artifact.format,
                    artifact.role,
                    artifact.conversion_id,
                ]
            ).lower()
            if resolved_filters.search.lower() not in haystack:
                return False
        return True

    filtered = [artifact for artifact in artifacts if matches(artifact)]
    start = resolved_filters.offset
    end = start + resolved_filters.limit
    return filtered[start:end]


def get_output_artifact(session: Session, output_id: str) -> OutputArtifact | None:
    backfill_output_artifacts(session)
    statement = (
        select(OutputArtifact)
        .options(
            selectinload(OutputArtifact.conversion),
            selectinload(OutputArtifact.output_actions),
        )
        .where(OutputArtifact.id == output_id)
    )
    artifact = session.scalar(statement)
    if artifact is None:
        return None

    if artifact.conversion is not None:
        sync_output_artifacts_for_conversion(session, artifact.conversion, commit=True)
        statement = (
            select(OutputArtifact)
            .options(
                selectinload(OutputArtifact.conversion),
                selectinload(OutputArtifact.output_actions),
            )
            .where(OutputArtifact.id == output_id)
        )
        return session.scalar(statement)
    return artifact


def get_output_artifact_or_raise(session: Session, output_id: str) -> OutputArtifact:
    artifact = get_output_artifact(session, output_id)
    if artifact is None:
        raise OutputArtifactNotFoundError(f"output artifact not found: {output_id}")
    return artifact


def resolve_output_artifact_path(artifact: OutputArtifact) -> Path:
    if artifact.conversion is None or artifact.conversion.output_path is None:
        raise OutputArtifactContentUnavailableError(
            f"output artifact has no conversion output directory: {artifact.id}"
        )

    artifact_path = Path(artifact.conversion.output_path) / artifact.relative_path
    if not artifact_path.exists() or not artifact_path.is_file():
        raise OutputArtifactContentUnavailableError(
            f"output artifact content is unavailable: {artifact.id}"
        )

    return artifact_path
