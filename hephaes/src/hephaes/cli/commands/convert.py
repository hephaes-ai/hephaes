from __future__ import annotations

import argparse

from ...workspace import WorkspaceError
from ..common import add_workspace_argument, open_workspace, print_json


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    convert_parser = subparsers.add_parser(
        "convert",
        help="Run a local conversion and register emitted outputs in the workspace.",
    )
    convert_parser.add_argument(
        "source",
        help="Registered asset id, registered asset path, or direct local file path.",
    )
    add_workspace_argument(convert_parser)
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
    convert_parser.set_defaults(handler=handle_convert)


def handle_convert(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    if (args.config is None) == (args.spec_document is None):
        raise WorkspaceError("provide exactly one of --config or --spec-document")

    outputs = workspace.run_conversion(
        args.source,
        saved_config_selector=args.config,
        spec_document=args.spec_document,
        output_dir=args.output_dir,
        max_workers=args.max_workers,
    )
    print_json(
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
        }
    )
    return 0
