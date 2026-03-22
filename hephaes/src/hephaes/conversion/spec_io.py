from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .._converter_helpers import _json_default
from ..models import ConversionSpec

CONVERSION_SPEC_DOCUMENT_VERSION = 2


class ConversionSpecDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec_version: int = Field(default=CONVERSION_SPEC_DOCUMENT_VERSION, ge=1)
    spec: ConversionSpec
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_version(self) -> "ConversionSpecDocument":
        if self.spec_version > CONVERSION_SPEC_DOCUMENT_VERSION:
            raise ValueError(
                f"unsupported conversion spec document version: {self.spec_version}"
            )
        return self


def _read_text_payload(payload: str | Path) -> str:
    if isinstance(payload, Path):
        return payload.read_text()

    stripped = payload.strip()
    if stripped.startswith("{") or stripped.startswith("[") or "\n" in payload:
        return payload

    try:
        candidate_path = Path(payload)
        if candidate_path.exists():
            return candidate_path.read_text()
    except OSError:
        return payload
    return payload


def _load_payload_from_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise ValueError("conversion spec payload is empty")

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        loaded = yaml.safe_load(stripped)
        if loaded is None:
            raise ValueError("conversion spec payload is empty")
        return loaded


def _migrate_source_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload

    normalized = deepcopy(payload)
    if "kind" not in normalized:
        if "topic" in normalized or "field_path" in normalized:
            normalized["kind"] = "path"
        elif "key" in normalized:
            normalized["kind"] = "metadata"
        elif "value" in normalized and "sources" not in normalized:
            normalized["kind"] = "constant"

    if "sources" in normalized and isinstance(normalized["sources"], list):
        normalized["sources"] = [
            _migrate_source_payload(item) for item in normalized["sources"]
        ]
    return normalized


def _migrate_row_strategy_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload

    normalized = deepcopy(payload)
    if "kind" in normalized:
        return normalized
    if "trigger_topic" in normalized or "joins" in normalized:
        normalized["kind"] = "trigger"
    elif "freq_hz" in normalized or "method" in normalized:
        normalized["kind"] = "resample"
    elif "topic" in normalized:
        normalized["kind"] = "per-message"
    return normalized


def migrate_conversion_spec_payload(
    payload: dict[str, Any],
    *,
    source_version: int | None = None,
    target_version: int = CONVERSION_SPEC_DOCUMENT_VERSION,
) -> dict[str, Any]:
    normalized = deepcopy(payload)
    if source_version is not None and source_version > target_version:
        raise ValueError(
            f"unsupported conversion spec payload version: {source_version}"
        )

    if "schema_spec" in normalized and "schema" not in normalized:
        normalized["schema"] = normalized.pop("schema_spec")

    if "schema" not in normalized:
        schema_name = normalized.pop("schema_name", None)
        schema_version = normalized.pop("schema_version", None)
        if schema_name is not None or schema_version is not None:
            schema_payload: dict[str, Any] = {}
            if schema_name is not None:
                schema_payload["name"] = schema_name
            if schema_version is not None:
                schema_payload["version"] = schema_version
            normalized["schema"] = schema_payload

    if "spec_version" in normalized and "spec" not in normalized:
        normalized.pop("spec_version", None)

    if "assembly" in normalized and "row_strategy" not in normalized:
        normalized["row_strategy"] = _migrate_row_strategy_payload(normalized["assembly"])

    if "row_strategy" in normalized:
        normalized["row_strategy"] = _migrate_row_strategy_payload(normalized["row_strategy"])

    features = normalized.get("features")
    if isinstance(features, dict):
        for feature_payload in features.values():
            if isinstance(feature_payload, dict) and "source" in feature_payload:
                feature_payload["source"] = _migrate_source_payload(feature_payload["source"])

    labels = normalized.get("labels")
    if isinstance(labels, dict) and "source" in labels:
        labels["source"] = _migrate_source_payload(labels["source"])

    if target_version != CONVERSION_SPEC_DOCUMENT_VERSION:
        raise ValueError(
            f"unsupported conversion spec target version: {target_version}"
        )

    return normalized


def build_conversion_spec_document(
    spec: ConversionSpec,
    *,
    metadata: dict[str, Any] | None = None,
    spec_version: int = CONVERSION_SPEC_DOCUMENT_VERSION,
) -> ConversionSpecDocument:
    return ConversionSpecDocument(
        spec_version=spec_version,
        spec=spec,
        metadata=dict(metadata or {}),
    )


def load_conversion_spec(payload: ConversionSpec | dict[str, Any] | str | Path) -> ConversionSpec:
    if isinstance(payload, ConversionSpec):
        return payload

    if isinstance(payload, (str, Path)):
        payload = _load_payload_from_text(_read_text_payload(payload))

    if not isinstance(payload, dict):
        raise TypeError("conversion spec payload must be a mapping, string, or path")

    if "spec" in payload:
        return load_conversion_spec_document(payload).spec

    normalized = migrate_conversion_spec_payload(payload)
    return ConversionSpec.model_validate(normalized)


def load_conversion_spec_document(
    payload: ConversionSpecDocument | dict[str, Any] | str | Path,
) -> ConversionSpecDocument:
    if isinstance(payload, ConversionSpecDocument):
        return payload

    if isinstance(payload, (str, Path)):
        payload = _load_payload_from_text(_read_text_payload(payload))

    if not isinstance(payload, dict):
        raise TypeError("conversion spec document payload must be a mapping, string, or path")

    if "spec" not in payload:
        spec = load_conversion_spec(payload)
        return build_conversion_spec_document(spec)

    spec_payload = payload["spec"]
    metadata = payload.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise TypeError("conversion spec document metadata must be a mapping")

    spec_version = payload.get("spec_version", CONVERSION_SPEC_DOCUMENT_VERSION)
    spec = load_conversion_spec(spec_payload)
    return ConversionSpecDocument(
        spec_version=int(spec_version),
        spec=spec,
        metadata=dict(metadata),
    )


def dump_conversion_spec(
    spec: ConversionSpec,
    *,
    indent: int = 2,
    by_alias: bool = True,
) -> str:
    payload = spec.model_dump(by_alias=by_alias, mode="json")
    return json.dumps(payload, indent=indent, sort_keys=True, default=_json_default)


def dump_conversion_spec_document(
    document: ConversionSpecDocument,
    *,
    indent: int = 2,
    by_alias: bool = True,
    format: str = "json",
) -> str:
    payload = document.model_dump(by_alias=by_alias, mode="json")
    if format == "json":
        return json.dumps(payload, indent=indent, sort_keys=True, default=_json_default)
    if format == "yaml":
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    raise ValueError("format must be 'json' or 'yaml'")


def migrate_conversion_spec_document(
    document: ConversionSpecDocument | dict[str, Any] | str | Path,
    *,
    target_version: int = CONVERSION_SPEC_DOCUMENT_VERSION,
) -> ConversionSpecDocument:
    loaded = load_conversion_spec_document(document)
    if loaded.spec_version > target_version:
        raise ValueError(
            f"unsupported conversion spec document version: {loaded.spec_version}"
        )
    if loaded.spec_version == target_version:
        return loaded
    return loaded.model_copy(update={"spec_version": target_version})
