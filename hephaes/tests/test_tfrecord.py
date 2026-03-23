"""Tests for TFRecord helpers and writers."""
from __future__ import annotations

import base64

import pytest

from hephaes.models import TFRecordOutputConfig
from hephaes.outputs import EpisodeContext, RecordBatch
from hephaes.outputs.tfrecord_writer import TFRecordDatasetWriter
from hephaes.tfrecord import stream_tfrecord_rows


class TestTFRecordDatasetWriter:
    def test_writes_rows_and_preserves_nulls(self, tmp_path):
        context = EpisodeContext(
            episode_id="ep001",
            source_path=tmp_path / "source.mcap",
            ros_version="ROS2",
            field_names=["cmd_vel", "odom"],
            resample=None,
            output=TFRecordOutputConfig(),
        )

        with TFRecordDatasetWriter(
            output_dir=tmp_path,
            context=context,
            config=TFRecordOutputConfig(),
        ) as writer:
            writer.write_batch(
                RecordBatch(
                    timestamps=[1, 2],
                    field_data={
                        "cmd_vel": [{"v": 1}, None],
                        "odom": [None, {"pose": 2}],
                    },
                )
            )

        rows = list(stream_tfrecord_rows(tmp_path / "ep001.tfrecord"))
        assert rows == [
            {"timestamp_ns": 1, "cmd_vel__present": 1, "cmd_vel__v": 1, "odom__present": 0},
            {"timestamp_ns": 2, "cmd_vel__present": 0, "odom__present": 1, "odom__pose": 2},
        ]

    def test_reads_gzip_compressed_tfrecord(self, tmp_path):
        config = TFRecordOutputConfig(compression="gzip")
        context = EpisodeContext(
            episode_id="ep_gzip",
            source_path=tmp_path / "source.mcap",
            ros_version="ROS2",
            field_names=["camera"],
            resample=None,
            output=config,
        )

        with TFRecordDatasetWriter(
            output_dir=tmp_path,
            context=context,
            config=config,
        ) as writer:
            writer.write_batch(
                RecordBatch(
                    timestamps=[5],
                    field_data={"camera": [{"frame": 1}]},
                )
            )

        rows = list(stream_tfrecord_rows(tmp_path / "ep_gzip.tfrecord"))
        assert rows == [{"timestamp_ns": 5, "camera__present": 1, "camera__frame": 1}]

    def test_writes_bytes_and_float_features(self, tmp_path):
        context = EpisodeContext(
            episode_id="ep_bytes",
            source_path=tmp_path / "source.mcap",
            ros_version="ROS2",
            field_names=["camera", "imu"],
            resample=None,
            output=TFRecordOutputConfig(),
        )

        encoded_bytes = {
            "__bytes__": True,
            "encoding": "base64",
            "value": base64.b64encode(b"jpeg-bytes").decode("ascii"),
        }
        with TFRecordDatasetWriter(
            output_dir=tmp_path,
            context=context,
            config=TFRecordOutputConfig(),
        ) as writer:
            writer.write_batch(
                RecordBatch(
                    timestamps=[7],
                    field_data={
                        "camera": [{"format": "jpeg", "data": encoded_bytes}],
                        "imu": [{"accel": [0.25, 0.5, 1.0]}],
                    },
                )
            )

        rows = list(stream_tfrecord_rows(tmp_path / "ep_bytes.tfrecord"))
        assert rows == [
            {
                "timestamp_ns": 7,
                "camera__present": 1,
                "camera__format": b"jpeg",
                "camera__data": b"jpeg-bytes",
                "imu__present": 1,
                "imu__accel": [0.25, 0.5, 1.0],
            }
        ]

    def test_round_trips_negative_int_features(self, tmp_path):
        context = EpisodeContext(
            episode_id="ep_negative",
            source_path=tmp_path / "source.mcap",
            ros_version="ROS2",
            field_names=["cmd_vel"],
            resample=None,
            output=TFRecordOutputConfig(),
        )

        with TFRecordDatasetWriter(
            output_dir=tmp_path,
            context=context,
            config=TFRecordOutputConfig(),
        ) as writer:
            writer.write_batch(
                RecordBatch(
                    timestamps=[9],
                    field_data={"cmd_vel": [{"reverse": -3}]},
                )
            )

        rows = list(stream_tfrecord_rows(tmp_path / "ep_negative.tfrecord"))
        assert rows == [
            {"timestamp_ns": 9, "cmd_vel__present": 1, "cmd_vel__reverse": -3}
        ]

    def test_preserves_singleton_sequence_shape(self, tmp_path):
        context = EpisodeContext(
            episode_id="ep_singleton",
            source_path=tmp_path / "source.mcap",
            ros_version="ROS2",
            field_names=["imu"],
            resample=None,
            output=TFRecordOutputConfig(),
        )

        with TFRecordDatasetWriter(
            output_dir=tmp_path,
            context=context,
            config=TFRecordOutputConfig(),
        ) as writer:
            writer.write_batch(
                RecordBatch(
                    timestamps=[11, 12],
                    field_data={
                        "imu": [{"accel": [0.25]}, {"accel": []}],
                    },
                )
            )

        rows = list(stream_tfrecord_rows(tmp_path / "ep_singleton.tfrecord"))
        assert rows == [
            {"timestamp_ns": 11, "imu__present": 1, "imu__accel": [0.25]},
            {"timestamp_ns": 12, "imu__present": 1, "imu__accel": []},
        ]

    def test_defaults_image_payload_data_to_bytes(self, tmp_path):
        context = EpisodeContext(
            episode_id="ep_image_bytes",
            source_path=tmp_path / "source.mcap",
            ros_version="ROS2",
            field_names=["camera"],
            resample=None,
            output=TFRecordOutputConfig(),
        )

        with TFRecordDatasetWriter(
            output_dir=tmp_path,
            context=context,
            config=TFRecordOutputConfig(),
        ) as writer:
            writer.write_batch(
                RecordBatch(
                    timestamps=[21],
                    field_data={
                        "camera": [
                            {
                                "height": 1,
                                "width": 2,
                                "encoding": "mono8",
                                "step": 2,
                                "data": [7, 9],
                            }
                        ]
                    },
                )
            )

        rows = list(stream_tfrecord_rows(tmp_path / "ep_image_bytes.tfrecord"))
        assert rows == [
            {
                "timestamp_ns": 21,
                "camera__present": 1,
                "camera__height": 1,
                "camera__width": 2,
                "camera__encoding": b"mono8",
                "camera__step": 2,
                "camera__data": b"\x07\x09",
            }
        ]

    def test_legacy_image_payload_contract_keeps_list_representation(self, tmp_path):
        config = TFRecordOutputConfig(image_payload_contract="legacy_list_v1")
        context = EpisodeContext(
            episode_id="ep_image_legacy",
            source_path=tmp_path / "source.mcap",
            ros_version="ROS2",
            field_names=["camera"],
            resample=None,
            output=config,
        )

        with TFRecordDatasetWriter(
            output_dir=tmp_path,
            context=context,
            config=config,
        ) as writer:
            writer.write_batch(
                RecordBatch(
                    timestamps=[22],
                    field_data={
                        "camera": [
                            {
                                "height": 1,
                                "width": 2,
                                "encoding": "mono8",
                                "step": 2,
                                "data": [7, 9],
                            }
                        ]
                    },
                )
            )

        rows = list(stream_tfrecord_rows(tmp_path / "ep_image_legacy.tfrecord"))
        assert rows == [
            {
                "timestamp_ns": 22,
                "camera__present": 1,
                "camera__height": 1,
                "camera__width": 2,
                "camera__encoding": b"mono8",
                "camera__step": 2,
                "camera__data": [7, 9],
            }
        ]

    def test_non_image_sequence_remains_sequence_in_bytes_contract(self, tmp_path):
        context = EpisodeContext(
            episode_id="ep_not_image",
            source_path=tmp_path / "source.mcap",
            ros_version="ROS2",
            field_names=["imu"],
            resample=None,
            output=TFRecordOutputConfig(),
        )

        with TFRecordDatasetWriter(
            output_dir=tmp_path,
            context=context,
            config=TFRecordOutputConfig(),
        ) as writer:
            writer.write_batch(
                RecordBatch(
                    timestamps=[23],
                    field_data={
                        "imu": [{"accel": [0.1, 0.2, 0.3]}],
                    },
                )
            )

        rows = list(stream_tfrecord_rows(tmp_path / "ep_not_image.tfrecord"))
        assert rows[0]["timestamp_ns"] == 23
        assert rows[0]["imu__present"] == 1
        assert rows[0]["imu__accel"] == pytest.approx([0.1, 0.2, 0.3])

    def test_rejects_invalid_image_data_outside_uint8_range(self, tmp_path):
        context = EpisodeContext(
            episode_id="ep_invalid_image",
            source_path=tmp_path / "source.mcap",
            ros_version="ROS2",
            field_names=["camera"],
            resample=None,
            output=TFRecordOutputConfig(),
        )

        with TFRecordDatasetWriter(
            output_dir=tmp_path,
            context=context,
            config=TFRecordOutputConfig(),
        ) as writer:
            with pytest.raises(ValueError, match="uint8 range"):
                writer.write_batch(
                    RecordBatch(
                        timestamps=[24],
                        field_data={
                            "camera": [
                                {
                                    "height": 1,
                                    "width": 1,
                                    "encoding": "mono8",
                                    "step": 1,
                                    "data": [999],
                                }
                            ]
                        },
                    )
                )
