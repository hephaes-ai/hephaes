from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .conversion.introspection import inspect_bag
from .workspace import (
    AssetAlreadyRegisteredError,
    ConversionConfigAlreadyExistsError,
    InvalidAssetPathError,
    OutputArtifactNotFoundError,
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
        help="Asset file or directory paths to register. Directories are walked recursively.",
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

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect the structure of a local asset.",
    )
    inspect_parser.add_argument(
        "selector",
        help="Registered asset id, registered asset path, or direct local file path.",
    )
    inspect_parser.add_argument(
        "--workspace",
        help="Workspace root or any path inside the target workspace.",
    )
    inspect_parser.add_argument(
        "--topic",
        dest="topics",
        action="append",
        default=[],
        help="Topic filter to inspect. Repeat for multiple topics.",
    )
    inspect_parser.add_argument(
        "--sample-n",
        type=int,
        default=8,
        help="Maximum number of sampled messages per topic.",
    )
    inspect_parser.add_argument(
        "--max-depth",
        type=int,
        default=4,
        help="Maximum traversal depth for nested payload inspection.",
    )
    inspect_parser.add_argument(
        "--max-sequence-items",
        type=int,
        default=4,
        help="Maximum number of sequence items to inspect per message.",
    )
    inspect_parser.add_argument(
        "--on-failure",
        choices=("skip", "warn", "fail"),
        default="warn",
        help="Decode failure policy while sampling messages.",
    )
    inspect_parser.set_defaults(handler=_handle_inspect)

    convert_parser = subparsers.add_parser(
        "convert",
        help="Run a local conversion and register emitted outputs in the workspace.",
    )
    convert_parser.add_argument(
        "source",
        help="Registered asset id, registered asset path, or direct local file path.",
    )
    convert_parser.add_argument(
        "--workspace",
        help="Workspace root or any path inside the target workspace.",
    )
    convert_parser.add_argument(
        "--config",
        help="Saved conversion config id or name.",
    )
    convert_parser.add_argument(
        "--spec-document",
        help="Path to a conversion spec or conversion spec document.",
    )
    convert_parser.add_argument(
        "--output-dir",
        help="Directory where converted outputs should be written.",
    )
    convert_parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Worker count for conversion.",
    )
    convert_parser.set_defaults(handler=_handle_convert)

    configs_parser = subparsers.add_parser(
        "configs",
        help="Manage saved conversion configs in the active workspace.",
    )
    configs_subparsers = configs_parser.add_subparsers(dest="configs_command")

    configs_ls_parser = configs_subparsers.add_parser(
        "ls",
        help="List saved conversion configs.",
    )
    configs_ls_parser.add_argument(
        "--workspace",
        help="Workspace root or any path inside the target workspace.",
    )
    configs_ls_parser.set_defaults(handler=_handle_list_configs)

    configs_save_parser = configs_subparsers.add_parser(
        "save",
        help="Save a conversion spec document into the workspace config store.",
    )
    configs_save_parser.add_argument("name", help="Saved config name.")
    configs_save_parser.add_argument(
        "spec_document",
        help="Path to a conversion spec or conversion spec document.",
    )
    configs_save_parser.add_argument(
        "--workspace",
        help="Workspace root or any path inside the target workspace.",
    )
    configs_save_parser.add_argument(
        "--description",
        help="Optional saved config description.",
    )
    configs_save_parser.set_defaults(handler=_handle_save_config)

    outputs_parser = subparsers.add_parser(
        "outputs",
        help="Inspect tracked output artifacts in the active workspace.",
    )
    outputs_subparsers = outputs_parser.add_subparsers(dest="outputs_command")

    outputs_ls_parser = outputs_subparsers.add_parser(
        "ls",
        help="List tracked output artifacts.",
    )
    outputs_ls_parser.add_argument(
        "--workspace",
        help="Workspace root or any path inside the target workspace.",
    )
    outputs_ls_parser.set_defaults(handler=_handle_list_outputs)

    outputs_show_parser = outputs_subparsers.add_parser(
        "show",
        help="Show one tracked output artifact.",
    )
    outputs_show_parser.add_argument("output_id", help="Tracked output artifact id.")
    outputs_show_parser.add_argument(
        "--workspace",
        help="Workspace root or any path inside the target workspace.",
    )
    outputs_show_parser.set_defaults(handler=_handle_show_output)

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
    except (
        WorkspaceError,
        InvalidAssetPathError,
        AssetAlreadyRegisteredError,
        ConversionConfigAlreadyExistsError,
        OutputArtifactNotFoundError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def entrypoint() -> None:
    raise SystemExit(main())


def _open_workspace(explicit_path: str | None) -> Workspace:
    if explicit_path is None:
        return Workspace.open()
    return Workspace.open(explicit_path)


def _resolve_inspect_path(selector: str, workspace_path: str | None) -> str:
    workspace: Workspace | None = None
    try:
        workspace = _open_workspace(workspace_path)
    except WorkspaceNotFoundError:
        workspace = None

    if workspace is not None:
        try:
            return workspace.resolve_asset(selector).file_path
        except WorkspaceError:
            pass

    return str(Path(selector).expanduser().resolve(strict=False))


def _handle_init(args: argparse.Namespace) -> int:
    workspace = Workspace.init(args.path, exist_ok=args.exist_ok)
    print(f"Initialized Hephaes workspace at {workspace.workspace_dir}")
    return 0


def _collect_asset_files(paths: list[str]) -> tuple[list[Path], list[Path]]:
    from .workspace import SUPPORTED_ASSET_FILE_TYPES

    explicit: list[Path] = []
    discovered: list[Path] = []
    for raw in paths:
        p = Path(raw).expanduser().resolve()
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and child.suffix.lstrip(".") in SUPPORTED_ASSET_FILE_TYPES:
                    discovered.append(child)
        else:
            explicit.append(p)
    return explicit, discovered


def _handle_add(args: argparse.Namespace) -> int:
    workspace = _open_workspace(args.workspace)
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
        display_path = asset.source_path or asset.file_path
        print(
            "\t".join(
                (
                    asset.id,
                    asset.indexing_status,
                    asset.file_type,
                    display_path,
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
        display_path = asset.source_path or asset.file_path
        print(
            "\t".join(
                (
                    asset.id,
                    asset.indexing_status,
                    asset.file_type,
                    str(asset.file_size),
                    last_indexed_at,
                    display_path,
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
                    "source_path": indexed_asset.source_path,
                    "message_count": metadata.message_count,
                    "topic_count": metadata.topic_count,
                    "duration": metadata.duration,
                    "sensor_types": metadata.sensor_types,
                },
                sort_keys=True,
            )
        )
    return 0


def _handle_inspect(args: argparse.Namespace) -> int:
    bag_path = _resolve_inspect_path(args.selector, args.workspace)
    inspection = inspect_bag(
        bag_path,
        topics=args.topics or None,
        sample_n=args.sample_n,
        max_depth=args.max_depth,
        max_sequence_items=args.max_sequence_items,
        on_failure=args.on_failure,
    )
    print(json.dumps(inspection.model_dump(mode="json"), sort_keys=True))
    return 0


def _handle_convert(args: argparse.Namespace) -> int:
    workspace = _open_workspace(args.workspace)
    if (args.config is None) == (args.spec_document is None):
        raise WorkspaceError("provide exactly one of --config or --spec-document")

    outputs = workspace.run_conversion(
        args.source,
        saved_config_selector=args.config,
        spec_document=args.spec_document,
        output_dir=args.output_dir,
        max_workers=args.max_workers,
    )
    print(
        json.dumps(
            {
                "output_count": len(outputs),
                "outputs": [
                    {
                        "id": output.id,
                        "format": output.format,
                        "role": output.role,
                        "output_path": output.output_path,
                        "saved_config_id": output.saved_config_id,
                        "source_asset_id": output.source_asset_id,
                        "source_asset_path": output.source_asset_path,
                        "manifest_available": output.manifest_available,
                        "report_available": output.report_available,
                    }
                    for output in outputs
                ],
            },
            sort_keys=True,
        )
    )
    return 0


def _handle_list_configs(args: argparse.Namespace) -> int:
    workspace = _open_workspace(args.workspace)
    configs = workspace.list_saved_conversion_configs()
    if not configs:
        print("No saved conversion configs.")
        return 0

    for config in configs:
        print(
            "\t".join(
                (
                    config.id,
                    str(config.spec_document_version),
                    config.name,
                    config.document_path,
                )
            )
        )
    return 0


def _handle_save_config(args: argparse.Namespace) -> int:
    workspace = _open_workspace(args.workspace)
    config = workspace.save_conversion_config(
        name=args.name,
        spec_document=args.spec_document,
        description=args.description,
    )
    print(
        "\t".join(
            (
                config.id,
                str(config.spec_document_version),
                config.name,
                config.document_path,
            )
        )
    )
    return 0


def _handle_list_outputs(args: argparse.Namespace) -> int:
    workspace = _open_workspace(args.workspace)
    outputs = workspace.list_output_artifacts()
    if not outputs:
        print("No tracked outputs.")
        return 0

    for output in outputs:
        print(
            "\t".join(
                (
                    output.id,
                    output.format,
                    output.role,
                    output.source_asset_id or output.source_asset_path or "-",
                    output.saved_config_id or "-",
                    output.output_path,
                )
            )
        )
    return 0


def _handle_show_output(args: argparse.Namespace) -> int:
    workspace = _open_workspace(args.workspace)
    output = workspace.get_output_artifact_or_raise(args.output_id)
    print(
        json.dumps(
            {
                "id": output.id,
                "source_asset_id": output.source_asset_id,
                "source_asset_path": output.source_asset_path,
                "saved_config_id": output.saved_config_id,
                "output_path": output.output_path,
                "relative_path": output.relative_path,
                "file_name": output.file_name,
                "format": output.format,
                "role": output.role,
                "size_bytes": output.size_bytes,
                "availability_status": output.availability_status,
                "manifest_available": output.manifest_available,
                "report_available": output.report_available,
                "metadata": output.metadata,
                "created_at": output.created_at.isoformat(),
                "updated_at": output.updated_at.isoformat(),
            },
            sort_keys=True,
        )
    )
    return 0
