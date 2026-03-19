"""Service helpers for output-scoped compute actions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db.models import OutputAction, OutputArtifact, utc_now
from app.services.outputs import (
    get_output_artifact_or_raise,
    sync_output_artifacts_for_conversion,
)


class OutputActionServiceError(Exception):
    """Base exception for output action service failures."""


class OutputActionNotFoundError(OutputActionServiceError):
    """Raised when an output action id is unknown."""


class OutputActionValidationError(OutputActionServiceError):
    """Raised when an action request is invalid for the target output."""


def get_output_action(session: Session, action_id: str) -> OutputAction | None:
    statement = (
        select(OutputAction)
        .options(
            selectinload(OutputAction.output_artifact).selectinload(OutputArtifact.conversion),
        )
        .where(OutputAction.id == action_id)
    )
    return session.scalar(statement)


def get_output_action_or_raise(session: Session, action_id: str) -> OutputAction:
    action = get_output_action(session, action_id)
    if action is None:
        raise OutputActionNotFoundError(f"output action not found: {action_id}")
    return action


def list_output_actions_for_output(session: Session, output_id: str) -> list[OutputAction]:
    get_output_artifact_or_raise(session, output_id)
    statement = (
        select(OutputAction)
        .options(
            selectinload(OutputAction.output_artifact).selectinload(OutputArtifact.conversion),
        )
        .where(OutputAction.output_artifact_id == output_id)
        .order_by(OutputAction.created_at.desc(), OutputAction.id.desc())
    )
    return list(session.scalars(statement).all())


def _result_output_dir(action_id: str) -> Path:
    settings = get_settings()
    return settings.outputs_dir / "actions" / action_id


def _write_result_summary(action_id: str, payload: dict[str, Any]) -> Path:
    output_dir = _result_output_dir(action_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "result.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_dir


def _mark_action_running(session: Session, action: OutputAction) -> OutputAction:
    if action.started_at is None:
        action.started_at = utc_now()
    action.status = "running"
    action.finished_at = None
    action.error_message = None
    action.updated_at = utc_now()
    session.commit()
    return get_output_action_or_raise(session, action.id)


def _mark_action_succeeded(
    session: Session,
    action: OutputAction,
    *,
    result: dict[str, Any],
    output_path: str | None,
) -> OutputAction:
    if action.started_at is None:
        action.started_at = utc_now()
    action.status = "succeeded"
    action.result_json = dict(result)
    action.output_path = output_path
    action.error_message = None
    action.finished_at = utc_now()
    action.updated_at = utc_now()
    session.commit()
    return get_output_action_or_raise(session, action.id)


def _mark_action_failed(session: Session, action: OutputAction, *, error_message: str) -> OutputAction:
    if action.started_at is None:
        action.started_at = utc_now()
    action.status = "failed"
    action.error_message = error_message
    action.finished_at = utc_now()
    action.updated_at = utc_now()
    session.commit()
    return get_output_action_or_raise(session, action.id)


def _validate_action_request(artifact: OutputArtifact, *, action_type: str) -> None:
    if action_type != "refresh_metadata":
        raise OutputActionValidationError(f"unsupported output action type: {action_type}")

    if artifact.conversion is None:
        raise OutputActionValidationError(f"output artifact has no linked conversion: {artifact.id}")


def _execute_refresh_metadata(session: Session, action: OutputAction) -> OutputAction:
    artifact = get_output_artifact_or_raise(session, action.output_artifact_id)
    if artifact.conversion is None:
        raise OutputActionValidationError(f"output artifact has no linked conversion: {artifact.id}")

    sync_output_artifacts_for_conversion(session, artifact.conversion, commit=True)
    refreshed_artifact = get_output_artifact_or_raise(session, artifact.id)

    result_payload = {
        "output_id": refreshed_artifact.id,
        "availability_status": refreshed_artifact.availability_status,
        "size_bytes": refreshed_artifact.size_bytes,
        "metadata": dict(refreshed_artifact.metadata_json),
        "relative_path": refreshed_artifact.relative_path,
    }
    output_dir = _write_result_summary(action.id, result_payload)

    return _mark_action_succeeded(
        session,
        action,
        result=result_payload,
        output_path=str(output_dir),
    )


class OutputActionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_action(
        self,
        *,
        output_id: str,
        action_type: str,
        config: dict[str, Any] | None = None,
    ) -> OutputAction:
        artifact = get_output_artifact_or_raise(self.session, output_id)
        _validate_action_request(artifact, action_type=action_type)

        action = OutputAction(
            output_artifact_id=artifact.id,
            action_type=action_type,
            status="queued",
            config_json=dict(config or {}),
            result_json={},
            output_path=None,
            error_message=None,
            started_at=None,
            finished_at=None,
        )
        self.session.add(action)
        self.session.commit()

        action = _mark_action_running(self.session, action)

        try:
            if action.action_type == "refresh_metadata":
                return _execute_refresh_metadata(self.session, action)
            raise OutputActionValidationError(f"unsupported output action type: {action.action_type}")
        except Exception as exc:
            self.session.rollback()
            failed_action = get_output_action_or_raise(self.session, action.id)
            if isinstance(exc, OutputActionServiceError):
                return _mark_action_failed(self.session, failed_action, error_message=str(exc))
            return _mark_action_failed(self.session, failed_action, error_message=str(exc))
