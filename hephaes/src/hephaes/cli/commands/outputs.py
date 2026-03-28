from __future__ import annotations

import argparse

from ..common import add_workspace_argument, open_workspace, print_json


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    outputs_parser = subparsers.add_parser(
        "outputs",
        help="Inspect tracked output artifacts in the active workspace.",
    )
    outputs_subparsers = outputs_parser.add_subparsers(dest="outputs_command")

    outputs_ls_parser = outputs_subparsers.add_parser(
        "ls",
        help="List tracked output artifacts.",
    )
    add_workspace_argument(outputs_ls_parser)
    outputs_ls_parser.set_defaults(handler=handle_list_outputs)

    outputs_show_parser = outputs_subparsers.add_parser(
        "show",
        help="Show one tracked output artifact.",
    )
    outputs_show_parser.add_argument("output_id", help="Tracked output artifact id.")
    add_workspace_argument(outputs_show_parser)
    outputs_show_parser.set_defaults(handler=handle_show_output)


def handle_list_outputs(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    outputs = workspace.list_output_artifacts()
    if not outputs:
        print("No tracked outputs.")
        return 0

    for output in outputs:
        print(
            "\t".join(
                (
                    output.id,
                    output.conversion_run_id or "-",
                    output.format,
                    output.role,
                    output.source_asset_id or output.source_asset_path or "-",
                    output.saved_config_id or "-",
                    output.output_path,
                )
            )
        )
    return 0


def handle_show_output(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    output = workspace.get_output_artifact_or_raise(args.output_id)
    print_json(
        {
            "id": output.id,
            "conversion_run_id": output.conversion_run_id,
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
        }
    )
    return 0
