from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..workspace import Workspace, WorkspaceError, WorkspaceNotFoundError


def add_workspace_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        help="Workspace root or any path inside the target workspace.",
    )


def open_workspace(explicit_path: str | None) -> Workspace:
    if explicit_path is None:
        return Workspace.open()
    return Workspace.open(explicit_path)


def resolve_inspect_path(selector: str, workspace_path: str | None) -> str:
    workspace: Workspace | None = None
    try:
        workspace = open_workspace(workspace_path)
    except WorkspaceNotFoundError:
        workspace = None

    if workspace is not None:
        try:
            return workspace.resolve_asset(selector).file_path
        except WorkspaceError:
            pass

    return str(Path(selector).expanduser().resolve(strict=False))


def print_json(payload: object) -> None:
    print(json.dumps(payload, sort_keys=True))
