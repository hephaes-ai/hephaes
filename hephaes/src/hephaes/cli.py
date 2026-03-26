from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import __version__
from .workspace import (
    AssetAlreadyRegisteredError,
    InvalidAssetPathError,
    Workspace,
    WorkspaceAlreadyExistsError,
    WorkspaceError,
    WorkspaceNotFoundError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hephaes",
        description="Local workspace and dataset tooling for Hephaes.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a local Hephaes workspace.",
    )
    init_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory where the workspace should be created.",
    )
    init_parser.add_argument(
        "--exist-ok",
        action="store_true",
        help="Allow initialization when the workspace already exists.",
    )
    init_parser.set_defaults(handler=_handle_init)

    add_parser = subparsers.add_parser(
        "add",
        help="Register one or more local assets in the active workspace.",
    )
    add_parser.add_argument(
        "paths",
        nargs="+",
        help="Asset file paths to register.",
    )
    add_parser.add_argument(
        "--workspace",
        help="Workspace root or any path inside the target workspace.",
    )
    add_parser.add_argument(
        "--on-duplicate",
        choices=("error", "skip", "refresh"),
        default="error",
        help="Duplicate asset behavior.",
    )
    add_parser.set_defaults(handler=_handle_add)

    index_parser = subparsers.add_parser(
        "index",
        help="Index registered assets in the active workspace.",
    )
    index_parser.add_argument(
        "selectors",
        nargs="*",
        help="Asset ids or original file paths to index.",
    )
    index_parser.add_argument(
        "--workspace",
        help="Workspace root or any path inside the target workspace.",
    )
    index_parser.add_argument(
        "--all",
        action="store_true",
        help="Index every registered asset in the workspace.",
    )
    index_parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Worker count for bag profiling.",
    )
    index_parser.set_defaults(handler=_handle_index)

    ls_parser = subparsers.add_parser(
        "ls",
        help="List workspace records.",
    )
    ls_subparsers = ls_parser.add_subparsers(dest="ls_command")

    ls_assets_parser = ls_subparsers.add_parser(
        "assets",
        help="List registered assets in the active workspace.",
    )
    ls_assets_parser.add_argument(
        "--workspace",
        help="Workspace root or any path inside the target workspace.",
    )
    ls_assets_parser.set_defaults(handler=_handle_list_assets)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help(sys.stderr)
        return 1

    try:
        return int(handler(args))
    except (WorkspaceError, InvalidAssetPathError, AssetAlreadyRegisteredError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def entrypoint() -> None:
    raise SystemExit(main())


def _open_workspace(explicit_path: str | None) -> Workspace:
    if explicit_path is None:
        return Workspace.open()
    return Workspace.open(explicit_path)


def _handle_init(args: argparse.Namespace) -> int:
    workspace = Workspace.init(args.path, exist_ok=args.exist_ok)
    print(f"Initialized Hephaes workspace at {workspace.workspace_dir}")
    return 0


def _handle_add(args: argparse.Namespace) -> int:
    workspace = _open_workspace(args.workspace)
    registered = []
    for raw_path in args.paths:
        asset = workspace.register_asset(raw_path, on_duplicate=args.on_duplicate)
        registered.append(asset)

    for asset in registered:
        print(
            "\t".join(
                (
                    asset.id,
                    asset.indexing_status,
                    asset.file_type,
                    asset.file_path,
                )
            )
        )
    return 0


def _handle_list_assets(args: argparse.Namespace) -> int:
    workspace = _open_workspace(args.workspace)
    assets = workspace.list_assets()

    if not assets:
        print("No assets registered.")
        return 0

    for asset in assets:
        last_indexed_at = (
            asset.last_indexed_at.isoformat() if asset.last_indexed_at is not None else "-"
        )
        print(
            "\t".join(
                (
                    asset.id,
                    asset.indexing_status,
                    asset.file_type,
                    str(asset.file_size),
                    last_indexed_at,
                    asset.file_path,
                )
            )
        )
    return 0


def _handle_index(args: argparse.Namespace) -> int:
    workspace = _open_workspace(args.workspace)
    if args.max_workers < 1:
        raise WorkspaceError("--max-workers must be >= 1")

    if args.all:
        assets_to_index = workspace.list_assets()
    else:
        if not args.selectors:
            raise WorkspaceError("provide one or more asset selectors or use --all")
        assets_to_index = [workspace.resolve_asset(selector) for selector in args.selectors]

    if not assets_to_index:
        print("No assets to index.")
        return 0

    for asset in assets_to_index:
        indexed_asset = workspace.index_asset(asset.id, max_workers=args.max_workers)
        metadata = workspace.get_asset_metadata(indexed_asset.id)
        if metadata is None:
            raise WorkspaceError(f"indexed metadata missing for asset {indexed_asset.id}")
        print(
            json.dumps(
                {
                    "asset_id": indexed_asset.id,
                    "status": indexed_asset.indexing_status,
                    "file_path": indexed_asset.file_path,
                    "message_count": metadata.message_count,
                    "topic_count": metadata.topic_count,
                    "duration": metadata.duration,
                    "sensor_types": metadata.sensor_types,
                },
                sort_keys=True,
            )
        )
    return 0
