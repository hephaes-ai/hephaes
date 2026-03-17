from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.services import episodes as episode_service
from backend.app.services import indexing as indexing_service
from hephaes.models import BagMetadata, Message, Topic


def register_asset(client: TestClient, asset_path: Path):
    return client.post("/assets/register", json={"file_path": str(asset_path)})


BASE_TIME = datetime(2026, 3, 16, 10, 0, 0, tzinfo=UTC)
BASE_TIMESTAMP_NS = int(BASE_TIME.timestamp() * 1_000_000_000)
END_TIMESTAMP_NS = BASE_TIMESTAMP_NS + 5_000_000_000


def build_phase8_profile(asset_path: Path) -> BagMetadata:
    resolved_path = asset_path.resolve()
    return BagMetadata(
        compression_format="none",
        duration_seconds=5.0,
        end_time_iso=datetime.fromtimestamp(
            END_TIMESTAMP_NS / 1_000_000_000, tz=UTC
        ).isoformat().replace("+00:00", "Z"),
        end_timestamp=END_TIMESTAMP_NS,
        file_path=str(resolved_path),
        file_size_bytes=asset_path.stat().st_size,
        message_count=9,
        path=str(resolved_path),
        ros_version="ROS2",
        start_time_iso=BASE_TIME.isoformat().replace("+00:00", "Z"),
        start_timestamp=BASE_TIMESTAMP_NS,
        storage_format="mcap",
        topics=[
            Topic(
                message_count=3,
                message_type="sensor_msgs/Image",
                name="/camera/front/image_raw",
                rate_hz=1.0,
            ),
            Topic(
                message_count=4,
                message_type="sensor_msgs/Imu",
                name="/imu/data",
                rate_hz=2.0,
            ),
            Topic(
                message_count=2,
                message_type="sensor_msgs/PointCloud2",
                name="/lidar/points",
                rate_hz=1.0,
            ),
        ],
    )


def build_fake_messages() -> list[Message]:
    return [
        Message(
            timestamp=BASE_TIMESTAMP_NS,
            topic="/camera/front/image_raw",
            data={"width": 640, "height": 480, "encoding": "rgb8", "data": b"frame-0"},
        ),
        Message(
            timestamp=BASE_TIMESTAMP_NS + 500_000_000,
            topic="/imu/data",
            data={"linear_acceleration": {"x": 0.1, "y": 0.2, "z": 0.3}},
        ),
        Message(
            timestamp=BASE_TIMESTAMP_NS + 1_000_000_000,
            topic="/lidar/points",
            data={"points": [{"x": 1.0, "y": 2.0, "z": 3.0}], "frame_id": "lidar"},
        ),
        Message(
            timestamp=BASE_TIMESTAMP_NS + 1_500_000_000,
            topic="/imu/data",
            data={"linear_acceleration": {"x": 0.4, "y": 0.5, "z": 0.6}},
        ),
        Message(
            timestamp=BASE_TIMESTAMP_NS + 2_000_000_000,
            topic="/camera/front/image_raw",
            data={"width": 640, "height": 480, "encoding": "rgb8", "data": b"frame-1"},
        ),
        Message(
            timestamp=BASE_TIMESTAMP_NS + 2_500_000_000,
            topic="/imu/data",
            data={"linear_acceleration": {"x": 0.7, "y": 0.8, "z": 0.9}},
        ),
        Message(
            timestamp=BASE_TIMESTAMP_NS + 3_000_000_000,
            topic="/lidar/points",
            data={"points": [{"x": 4.0, "y": 5.0, "z": 6.0}], "frame_id": "lidar"},
        ),
        Message(
            timestamp=BASE_TIMESTAMP_NS + 4_000_000_000,
            topic="/camera/front/image_raw",
            data={"width": 640, "height": 480, "encoding": "rgb8", "data": b"frame-2"},
        ),
        Message(
            timestamp=BASE_TIMESTAMP_NS + 4_500_000_000,
            topic="/imu/data",
            data={"linear_acceleration": {"x": 1.0, "y": 1.1, "z": 1.2}},
        ),
    ]


class FakeReader:
    def __init__(self, messages: list[Message]) -> None:
        self._messages = messages

    def __enter__(self) -> "FakeReader":
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> bool:
        return False

    def iter_message_headers(self, topics: list[str] | None = None):
        selected_topics = set(topics) if topics else None
        for message in self._messages:
            if selected_topics is None or message.topic in selected_topics:
                yield message.topic, message.timestamp

    def read_messages(self, topics: list[str] | None = None):
        selected_topics = set(topics) if topics else None
        for message in self._messages:
            if selected_topics is None or message.topic in selected_topics:
                yield message


def index_phase8_asset(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
) -> str:
    asset_id = register_asset(client, sample_asset_file).json()["id"]
    monkeypatch.setattr(
        indexing_service,
        "profile_asset_file",
        lambda _file_path: build_phase8_profile(sample_asset_file),
    )
    monkeypatch.setattr(
        episode_service,
        "open_asset_reader",
        lambda _file_path: FakeReader(build_fake_messages()),
    )
    index_response = client.post(f"/assets/{asset_id}/index")
    assert index_response.status_code == 200
    return asset_id


def test_get_episode_detail_returns_streams_for_indexed_asset(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_phase8_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"

    response = client.get(f"/assets/{asset_id}/episodes/{episode_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == asset_id
    assert body["episode_id"] == episode_id
    assert body["duration_seconds"] == 5.0
    assert body["default_lane_count"] == 3
    assert body["has_visualizable_streams"] is True
    assert body["stream_count"] == 3
    assert [stream["source_topic"] for stream in body["streams"]] == [
        "/camera/front/image_raw",
        "/imu/data",
        "/lidar/points",
    ]
    assert body["streams"][0]["first_timestamp_ns"] == BASE_TIMESTAMP_NS
    assert body["streams"][0]["last_timestamp_ns"] == BASE_TIMESTAMP_NS + 4_000_000_000


def test_get_episode_detail_returns_404_for_unknown_episode(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_phase8_asset(client, monkeypatch, sample_asset_file)

    response = client.get(f"/assets/{asset_id}/episodes/not-a-real-episode")

    assert response.status_code == 404
    assert response.json() == {"detail": "episode not found: not-a-real-episode"}


def test_get_episode_timeline_returns_bucketed_lane_data(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_phase8_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"

    response = client.get(f"/assets/{asset_id}/episodes/{episode_id}/timeline", params={"bucket_count": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["bucket_count"] == 5
    assert body["duration_ns"] == 5_000_000_000
    assert [lane["source_topic"] for lane in body["lanes"]] == [
        "/camera/front/image_raw",
        "/imu/data",
        "/lidar/points",
    ]
    assert [bucket["event_count"] for bucket in body["lanes"][0]["buckets"]] == [1, 0, 1, 0, 1]
    assert [bucket["event_count"] for bucket in body["lanes"][1]["buckets"]] == [1, 1, 1, 0, 1]
    assert [bucket["event_count"] for bucket in body["lanes"][2]["buckets"]] == [0, 1, 0, 1, 0]


def test_get_episode_samples_returns_windowed_scalar_and_nearest_visual_samples(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_phase8_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"

    response = client.get(
        f"/assets/{asset_id}/episodes/{episode_id}/samples",
        params={
            "timestamp_ns": BASE_TIMESTAMP_NS + 2_200_000_000,
            "window_before_ns": 800_000_000,
            "window_after_ns": 400_000_000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_timestamp_ns"] == BASE_TIMESTAMP_NS + 2_200_000_000
    assert body["window_start_ns"] == BASE_TIMESTAMP_NS + 1_400_000_000
    assert body["window_end_ns"] == BASE_TIMESTAMP_NS + 2_600_000_000

    image_stream, imu_stream, lidar_stream = body["streams"]

    assert image_stream["selection_strategy"] == "nearest"
    assert image_stream["sample_count"] == 1
    assert image_stream["samples"][0]["timestamp_ns"] == BASE_TIMESTAMP_NS + 2_000_000_000
    assert image_stream["samples"][0]["metadata_json"]["width"] == 640

    assert imu_stream["selection_strategy"] == "window"
    assert imu_stream["sample_count"] == 2
    assert [sample["timestamp_ns"] for sample in imu_stream["samples"]] == [
        BASE_TIMESTAMP_NS + 1_500_000_000,
        BASE_TIMESTAMP_NS + 2_500_000_000,
    ]

    assert lidar_stream["selection_strategy"] == "nearest"
    assert lidar_stream["sample_count"] == 0


def test_get_episode_samples_rejects_unknown_stream_id(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_phase8_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"

    response = client.get(
        f"/assets/{asset_id}/episodes/{episode_id}/samples",
        params={
            "timestamp_ns": BASE_TIMESTAMP_NS,
            "stream_ids": "missing-stream",
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "episode stream not found: missing-stream"}


def test_episode_playback_routes_require_indexed_asset(client: TestClient, sample_asset_file: Path):
    asset_id = register_asset(client, sample_asset_file).json()["id"]
    episode_id = f"{asset_id}:default"

    detail_response = client.get(f"/assets/{asset_id}/episodes/{episode_id}")
    timeline_response = client.get(f"/assets/{asset_id}/episodes/{episode_id}/timeline")
    samples_response = client.get(
        f"/assets/{asset_id}/episodes/{episode_id}/samples",
        params={"timestamp_ns": BASE_TIMESTAMP_NS},
    )

    expected_detail = {
        "detail": f"asset must be indexed before episodes are available: {sample_asset_file.name}"
    }
    assert detail_response.status_code == 422
    assert detail_response.json() == expected_detail
    assert timeline_response.status_code == 422
    assert timeline_response.json() == expected_detail
    assert samples_response.status_code == 422
    assert samples_response.json() == expected_detail
