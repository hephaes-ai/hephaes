"""Tests for split, shard, and output layout helpers."""

from __future__ import annotations

from hephaes.conversion import (
    OutputRecord,
    partition_records_for_shards,
    partition_records_for_split,
    render_output_filename,
)
from hephaes.models import SplitSpec


def _make_records() -> list[OutputRecord]:
    return [
        OutputRecord(
            timestamp_ns=ts,
            field_data={"value": idx},
            presence_data={"value": 1},
        )
        for idx, ts in enumerate([30, 10, 20, 50, 40])
    ]


def test_partition_records_for_split_time_is_chronological():
    split = SplitSpec(
        strategy="time",
        train_fraction=0.4,
        val_fraction=0.2,
        test_fraction=0.4,
    )

    partitions = partition_records_for_split(_make_records(), split)

    assert list(partitions) == ["train", "val", "test"]
    assert [record.timestamp_ns for record in partitions["train"]] == [10, 20]
    assert [record.timestamp_ns for record in partitions["val"]] == [30]
    assert [record.timestamp_ns for record in partitions["test"]] == [40, 50]


def test_partition_records_for_split_random_is_seeded():
    split = SplitSpec(
        strategy="random",
        train_fraction=0.4,
        val_fraction=0.2,
        test_fraction=0.4,
        seed=7,
    )

    first = partition_records_for_split(_make_records(), split)
    second = partition_records_for_split(_make_records(), split)

    assert first == second
    assert sum(len(records) for records in first.values()) == 5
    assert sorted(record.timestamp_ns for records in first.values() for record in records) == [
        10,
        20,
        30,
        40,
        50,
    ]


def test_partition_records_for_shards_keeps_contiguous_groups():
    records = _make_records()
    shards = partition_records_for_shards(records, 3)

    assert [len(shard) for shard in shards] == [2, 2, 1]
    assert [record.timestamp_ns for record in shards[0]] == [30, 10]
    assert [record.timestamp_ns for record in shards[1]] == [20, 50]
    assert [record.timestamp_ns for record in shards[2]] == [40]


def test_render_output_filename_supports_defaults_and_templates():
    assert (
        render_output_filename(
            episode_id="episode_0001",
            split_name="train",
            shard_index=0,
            num_shards=8,
            extension="tfrecord",
        )
        == "episode_0001-train-00000-of-00008.tfrecord"
    )
    assert (
        render_output_filename(
            episode_id="episode_0001",
            split_name="all",
            shard_index=0,
            num_shards=2,
            extension="tfrecord",
        )
        == "episode_0001-00000-of-00002.tfrecord"
    )
    assert (
        render_output_filename(
            episode_id="episode_0001",
            split_name="all",
            shard_index=0,
            num_shards=1,
            extension="parquet",
        )
        == "episode_0001.parquet"
    )
    assert (
        render_output_filename(
            episode_id="episode_0001",
            split_name="val",
            shard_index=3,
            num_shards=8,
            extension="tfrecord",
            filename_template="{split}-{shard:05d}-of-{num_shards:05d}.{extension}",
        )
        == "val-00003-of-00008.tfrecord"
    )
