from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.services import episodes as episode_service
from app.services import indexing as indexing_service
from app.services import visualization as visualization_service
from .test_api_episodes import (
    BASE_TIMESTAMP_NS,
    FakeReader,
    build_fake_messages,
    build_phase8_profile,
    register_asset,
)


def index_asset(client: TestClient, monkeypatch, sample_asset_file: Path) -> str:
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


def _patch_rrd_generation(monkeypatch):
    """Replace _generate_rrd with a stub that writes a small dummy file."""

    def fake_generate_rrd(asset_file_path, *, asset_id, episode_id, topics, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"FAKE-RRD-RECORDING")
        return output_path

    monkeypatch.setattr(visualization_service, "_generate_rrd", fake_generate_rrd)


def test_prepare_visualization_creates_job(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"
    _patch_rrd_generation(monkeypatch)

    response = client.post(f"/assets/{asset_id}/episodes/{episode_id}/prepare-visualization")

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["type"] == "prepare_visualization"
    assert body["job"]["status"] == "succeeded"
    assert asset_id in body["job"]["target_asset_ids_json"]
    assert body["job"]["config_json"]["episode_id"] == episode_id


def test_prepare_visualization_returns_404_for_unknown_asset(client: TestClient):
    response = client.post("/assets/nonexistent/episodes/ep1/prepare-visualization")

    assert response.status_code == 404


def test_prepare_visualization_returns_404_for_unknown_episode(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_asset(client, monkeypatch, sample_asset_file)
    _patch_rrd_generation(monkeypatch)

    response = client.post(f"/assets/{asset_id}/episodes/not-a-real-episode/prepare-visualization")

    assert response.status_code == 404


def test_viewer_source_returns_none_when_not_prepared(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"

    response = client.get(f"/assets/{asset_id}/episodes/{episode_id}/viewer-source")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "none"
    assert body["episode_id"] == episode_id
    assert body["source_url"] is None


def test_viewer_source_returns_404_for_unknown_episode(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_asset(client, monkeypatch, sample_asset_file)

    response = client.get(f"/assets/{asset_id}/episodes/not-a-real-episode/viewer-source")

    assert response.status_code == 404
    assert response.json() == {"detail": "episode not found: not-a-real-episode"}


def test_viewer_source_returns_ready_after_preparation(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"
    _patch_rrd_generation(monkeypatch)

    prepare_response = client.post(f"/assets/{asset_id}/episodes/{episode_id}/prepare-visualization")
    assert prepare_response.status_code == 200

    response = client.get(f"/assets/{asset_id}/episodes/{episode_id}/viewer-source")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["source_kind"] == "rrd_url"
    assert body["source_url"] == f"/visualizations/{asset_id}/{episode_id}/recording.rrd"
    assert body["job_id"] is not None
    assert body["viewer_version"] is not None
    assert body["recording_version"] is not None


def test_viewer_source_returns_failed_on_generation_error(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"

    def failing_generate_rrd(asset_file_path, *, asset_id, episode_id, topics, output_path):
        raise visualization_service.VisualizationGenerationError("test generation failure")

    monkeypatch.setattr(visualization_service, "_generate_rrd", failing_generate_rrd)

    prepare_response = client.post(f"/assets/{asset_id}/episodes/{episode_id}/prepare-visualization")
    assert prepare_response.status_code == 422

    response = client.get(f"/assets/{asset_id}/episodes/{episode_id}/viewer-source")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["job_id"] is not None
    assert body["error_message"] == "test generation failure"


def test_repeated_prepare_reuses_cached_job(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"
    _patch_rrd_generation(monkeypatch)

    first_response = client.post(f"/assets/{asset_id}/episodes/{episode_id}/prepare-visualization")
    assert first_response.status_code == 200
    first_job_id = first_response.json()["job"]["id"]

    second_response = client.post(f"/assets/{asset_id}/episodes/{episode_id}/prepare-visualization")
    assert second_response.status_code == 200
    second_job_id = second_response.json()["job"]["id"]

    assert first_job_id == second_job_id


def test_viewer_source_includes_version_metadata(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"
    _patch_rrd_generation(monkeypatch)

    client.post(f"/assets/{asset_id}/episodes/{episode_id}/prepare-visualization")

    response = client.get(f"/assets/{asset_id}/episodes/{episode_id}/viewer-source")

    assert response.status_code == 200
    body = response.json()
    assert body["viewer_version"] == visualization_service.get_settings().rerun_sdk_version
    assert body["recording_version"] == visualization_service.get_settings().rerun_recording_format_version


def test_stale_artifact_is_not_reported_as_ready_and_is_regenerated(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"
    _patch_rrd_generation(monkeypatch)

    first_response = client.post(f"/assets/{asset_id}/episodes/{episode_id}/prepare-visualization")
    assert first_response.status_code == 200
    first_job_id = first_response.json()["job"]["id"]

    metadata_path = visualization_service._artifact_metadata_path(asset_id, episode_id)
    metadata_path.write_text(
        """
        {
          "asset_id": "%s",
          "episode_id": "%s",
          "viewer_version": "0.0-stale",
          "recording_version": "0",
          "generated_at": "2026-03-16T10:00:00Z"
        }
        """
        % (asset_id, episode_id),
        encoding="utf-8",
    )

    source_response = client.get(f"/assets/{asset_id}/episodes/{episode_id}/viewer-source")
    assert source_response.status_code == 200
    source_body = source_response.json()
    assert source_body["status"] == "none"
    assert source_body["job_id"] == first_job_id
    assert "incompatible" in source_body["error_message"]

    second_response = client.post(f"/assets/{asset_id}/episodes/{episode_id}/prepare-visualization")
    assert second_response.status_code == 200
    second_job_id = second_response.json()["job"]["id"]

    assert second_job_id != first_job_id


def test_artifact_source_url_is_servable(
    client: TestClient,
    monkeypatch,
    sample_asset_file: Path,
):
    asset_id = index_asset(client, monkeypatch, sample_asset_file)
    episode_id = f"{asset_id}:default"
    _patch_rrd_generation(monkeypatch)

    client.post(f"/assets/{asset_id}/episodes/{episode_id}/prepare-visualization")

    source_response = client.get(f"/assets/{asset_id}/episodes/{episode_id}/viewer-source")
    source_url = source_response.json()["source_url"]

    artifact_response = client.get(source_url)

    assert artifact_response.status_code == 200
    assert artifact_response.content == b"FAKE-RRD-RECORDING"
