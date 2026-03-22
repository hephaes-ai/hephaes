from __future__ import annotations

import fnmatch
import glob
from pathlib import Path
from typing import Iterable

from ..models import InputDiscoverySpec

_BAG_SUFFIXES = {".bag", ".mcap"}


def _is_glob_pattern(value: str) -> bool:
    return any(token in value for token in ("*", "?", "["))


def _normalize_candidate(path: Path) -> Path:
    return path.resolve()


def _iter_directory_candidates(directory: Path, *, recursive: bool) -> list[Path]:
    iterator = directory.rglob("*") if recursive else directory.iterdir()
    return sorted(
        (candidate for candidate in iterator if candidate.is_file()),
        key=lambda candidate: str(candidate),
    )


def discover_input_paths(
    input_paths: Iterable[str | Path],
    *,
    recursive: bool = False,
) -> list[Path]:
    resolved: list[Path] = []
    seen: set[Path] = set()

    for raw_path in input_paths:
        path_text = str(raw_path)
        candidates: list[Path]

        if _is_glob_pattern(path_text):
            matches = sorted(
                glob.glob(path_text, recursive=recursive or "**" in path_text),
            )
            if not matches:
                raise FileNotFoundError(f"No input paths matched pattern: {path_text}")
            candidates = [Path(match) for match in matches]
        else:
            candidate = Path(raw_path).expanduser()
            if candidate.is_dir():
                candidates = _iter_directory_candidates(candidate, recursive=recursive)
            else:
                if not candidate.exists():
                    raise FileNotFoundError(f"Path not found: {candidate}")
                candidates = [candidate]

        for candidate in candidates:
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() not in _BAG_SUFFIXES:
                if _is_glob_pattern(path_text) or Path(raw_path).is_dir():
                    continue
                raise ValueError(f"Unsupported bag file extension: {candidate}")
            normalized = _normalize_candidate(candidate)
            if normalized in seen:
                continue
            seen.add(normalized)
            resolved.append(normalized)

    if not resolved:
        raise ValueError("No input bag files were discovered")

    return resolved


def discover_input_paths_from_spec(
    input_paths: Iterable[str | Path],
    discovery: InputDiscoverySpec | None = None,
) -> list[Path]:
    recursive = discovery.recursive if discovery is not None else False
    return discover_input_paths(input_paths, recursive=recursive)


def filter_topics(
    topics: dict[str, str],
    *,
    include_topics: Iterable[str] | None = None,
    exclude_topics: Iterable[str] | None = None,
) -> dict[str, str]:
    include_patterns = [pattern for pattern in (include_topics or []) if pattern]
    exclude_patterns = [pattern for pattern in (exclude_topics or []) if pattern]

    filtered: dict[str, str] = {}
    for topic, message_type in topics.items():
        if include_patterns and not any(fnmatch.fnmatchcase(topic, pattern) for pattern in include_patterns):
            continue
        if exclude_patterns and any(fnmatch.fnmatchcase(topic, pattern) for pattern in exclude_patterns):
            continue
        filtered[topic] = message_type

    return dict(sorted(filtered.items()))


def filter_topics_from_spec(
    topics: dict[str, str],
    discovery: InputDiscoverySpec | None = None,
) -> dict[str, str]:
    if discovery is None:
        return dict(sorted(topics.items()))
    return filter_topics(
        topics,
        include_topics=discovery.include_topics,
        exclude_topics=discovery.exclude_topics,
    )
