from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Sequence

from ..models import SplitSpec

_SPLIT_NAMES = ("train", "val", "test")


@dataclass(frozen=True)
class OutputRecord:
    timestamp_ns: int
    field_data: dict[str, Any | None]
    presence_data: dict[str, int]


def _fraction_counts(total: int, fractions: Sequence[float]) -> list[int]:
    raw_counts = [fraction * total for fraction in fractions]
    counts = [int(math.floor(value)) for value in raw_counts]
    remainder = total - sum(counts)

    if remainder <= 0:
        return counts

    fractional_parts = sorted(
        enumerate(raw_counts),
        key=lambda item: (item[1] - math.floor(item[1]), -item[0]),
        reverse=True,
    )
    for index, _value in fractional_parts[:remainder]:
        counts[index] += 1
    return counts


def partition_records_for_split(
    records: Sequence[OutputRecord],
    split: SplitSpec | None,
) -> dict[str, list[OutputRecord]]:
    ordered_records = list(records)
    if split is None or split.strategy == "none" or not ordered_records:
        return {"all": ordered_records}

    if (
        split.train_fraction is None
        or split.val_fraction is None
        or split.test_fraction is None
    ):
        return {"all": ordered_records}

    records_by_index = list(enumerate(ordered_records))
    if split.strategy == "random":
        rng = random.Random(0 if split.seed is None else split.seed)
        rng.shuffle(records_by_index)
    else:
        records_by_index.sort(key=lambda item: (item[1].timestamp_ns, item[0]))

    counts = _fraction_counts(
        len(records_by_index),
        [split.train_fraction, split.val_fraction, split.test_fraction],
    )
    assignments: dict[str, list[tuple[int, OutputRecord]]] = {name: [] for name in _SPLIT_NAMES}

    cursor = 0
    for split_name, count in zip(_SPLIT_NAMES, counts):
        selected = records_by_index[cursor:cursor + count]
        assignments[split_name] = selected
        cursor += count

    partitioned: dict[str, list[OutputRecord]] = {}
    for split_name, selected in assignments.items():
        if not selected:
            continue
        if split.strategy == "time":
            ordered_selected = sorted(selected, key=lambda item: (item[1].timestamp_ns, item[0]))
        else:
            ordered_selected = sorted(selected, key=lambda item: item[0])
        partitioned[split_name] = [record for _index, record in ordered_selected]

    return partitioned


def partition_records_for_shards(
    records: Sequence[OutputRecord],
    num_shards: int,
) -> list[list[OutputRecord]]:
    if num_shards < 1:
        raise ValueError("num_shards must be >= 1")

    ordered_records = list(records)
    if not ordered_records:
        return []

    shard_count = min(num_shards, len(ordered_records))
    base_size, remainder = divmod(len(ordered_records), shard_count)
    shards: list[list[OutputRecord]] = []
    cursor = 0
    for shard_index in range(shard_count):
        size = base_size + (1 if shard_index < remainder else 0)
        shard_rows = ordered_records[cursor:cursor + size]
        shards.append(list(shard_rows))
        cursor += size

    return shards


def _default_output_template(
    *,
    split_name: str,
    num_shards: int,
    has_multiple_shards: bool,
    extension: str,
) -> str:
    if has_multiple_shards:
        if split_name == "all":
            return f"{{episode_id}}-{{shard:05d}}-of-{{num_shards:05d}}.{extension}"
        return f"{{episode_id}}-{split_name}-{{shard:05d}}-of-{{num_shards:05d}}.{extension}"
    if split_name == "all":
        return f"{{episode_id}}.{extension}"
    return f"{{episode_id}}-{split_name}.{extension}"


def render_output_filename(
    *,
    episode_id: str,
    split_name: str,
    shard_index: int,
    num_shards: int,
    extension: str,
    filename_template: str | None = None,
) -> str:
    template = filename_template or _default_output_template(
        split_name=split_name,
        num_shards=num_shards,
        has_multiple_shards=num_shards > 1,
        extension=extension,
    )
    return template.format(
        episode_id=episode_id,
        split=split_name,
        shard=shard_index,
        shard_index=shard_index,
        num_shards=num_shards,
        extension=extension,
    )
