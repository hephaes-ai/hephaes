from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ...workspace import AssetAlreadyRegisteredError, WorkspaceError
from ..common import add_workspace_argument, open_workspace


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    add_parser = subparsers.add_parser(
        "add",
        help="Register one or more local assets in the active workspace.",
    )
    add_parser.add_argument(
        "paths",
        nargs="+",
        help="Asset file or directory paths to register. Directories are walked recursively.",
    )
    add_workspace_argument(add_parser)
    add_parser.add_argument(
        "--on-duplicate",
        choices=("error", "skip", "refresh"),
        default="error",
        help="Duplicate asset behavior.",
    )
    add_parser.set_defaults(handler=handle_add)

    index_parser = subparsers.add_parser(
        "index",
        help="Index registered assets in the active workspace.",
    )
    index_parser.add_argument(
        "selectors",
        nargs="*",
        help="Asset ids or original file paths to index.",
    )
    add_workspace_argument(index_parser)
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
    index_parser.set_defaults(handler=handle_index)


def register_ls(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    ls_assets_parser = subparsers.add_parser(
        "assets",
        help="List registered assets in the active workspace.",
    )
    add_workspace_argument(ls_assets_parser)
    ls_assets_parser.add_argument(
        "--tag",
        dest="tags",
        action="append",
        default=[],
        help="Filter assets that have the given tag. Repeat for multiple tags.",
    )
    ls_assets_parser.set_defaults(handler=handle_list_assets)


def _collect_asset_files(paths: list[str]) -> tuple[list[Path], list[Path]]:
    from ...workspace import SUPPORTED_ASSET_FILE_TYPES

    explicit: list[Path] = []
    discovered: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lstrip(".") in SUPPORTED_ASSET_FILE_TYPES:
                    discovered.append(child)
        else:
            explicit.append(path)
    return explicit, discovered


def handle_add(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    explicit_files, discovered_files = _collect_asset_files(args.paths)
    if not explicit_files and not discovered_files:
        print("No supported asset files found.", file=sys.stderr)
        return 1

    registered = []
    for file_path in explicit_files:
        asset = workspace.register_asset(file_path, on_duplicate=args.on_duplicate)
        registered.append(asset)
    for file_path in discovered_files:
        try:
            asset = workspace.register_asset(file_path, on_duplicate="error")
            registered.append(asset)
        except AssetAlreadyRegisteredError:
            print(f"Warning: skipping already registered asset: {file_path}", file=sys.stderr)

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


def handle_list_assets(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    assets = workspace.list_assets(tags=args.tags or None)

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


def handle_index(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
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
