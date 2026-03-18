import json
import re
from typing import Sequence

from .models import MappingTemplate, Topic


def _to_field_name(topic: str, used_names: set[str]) -> str:
    candidate = topic.strip("/")
    candidate = re.sub(r"[^a-zA-Z0-9]+", "_", candidate).strip("_").lower()
    if not candidate:
        candidate = "topic"

    field_name = candidate
    suffix = 2
    while field_name in used_names:
        field_name = f"{candidate}_{suffix}"
        suffix += 1

    used_names.add(field_name)
    return field_name


def _normalize_topic_names(topics: Sequence[Topic]) -> list[str]:
    if not topics:
        raise ValueError("topics must not be empty")

    seen: set[str] = set()
    normalized: list[str] = []
    for topic in topics:
        if not isinstance(topic, Topic):
            raise TypeError("topics must contain Topic objects")
        if not topic.name:
            raise ValueError("topic names must be non-empty")
        if topic.name not in seen:
            normalized.append(topic.name)
            seen.add(topic.name)
    return normalized


def build_mapping_template(
    topics: Sequence[Topic],
) -> MappingTemplate:
    topic_names = sorted(_normalize_topic_names(topics))

    used_field_names: set[str] = set()
    mapping: dict[str, list[str]] = {}
    for topic in topic_names:
        mapping[_to_field_name(topic, used_field_names)] = [topic]
    return MappingTemplate.model_validate(mapping)


def build_mapping_template_from_json(
    topics: Sequence[Topic],
    custom_mapping_json: str | dict[str, list[str]],
    *,
    strict_unknown_topics: bool = True,
    require_all_topics: bool = False,
) -> MappingTemplate:
    all_topics = set(_normalize_topic_names(topics))

    if isinstance(custom_mapping_json, str):
        try:
            mapping_payload = json.loads(custom_mapping_json)
        except json.JSONDecodeError as exc:
            raise ValueError("custom_mapping_json must be valid JSON") from exc
    else:
        mapping_payload = custom_mapping_json

    mapping_template = MappingTemplate.model_validate(mapping_payload)

    mapped_topics: set[str] = set()
    duplicate_topics: set[str] = set()
    for source_topics in mapping_template.root.values():
        mapped_topics.update(source_topics)
    seen_topics: set[str] = set()
    for source_topics in mapping_template.root.values():
        for source_topic in source_topics:
            if source_topic in seen_topics:
                duplicate_topics.add(source_topic)
            seen_topics.add(source_topic)

    missing_topics = sorted(all_topics - mapped_topics) if require_all_topics else []
    unknown_topics = sorted(mapped_topics - all_topics) if strict_unknown_topics else []
    if missing_topics or unknown_topics or duplicate_topics:
        details = []
        if missing_topics:
            details.append(f"missing topics: {missing_topics}")
        if unknown_topics:
            details.append(f"unknown topics: {unknown_topics}")
        if duplicate_topics:
            details.append(f"duplicate topics across targets: {sorted(duplicate_topics)}")
        raise ValueError("custom mapping is invalid; " + "; ".join(details))

    return mapping_template
