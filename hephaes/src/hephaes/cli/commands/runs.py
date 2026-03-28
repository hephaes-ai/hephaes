from __future__ import annotations

import argparse

from ..common import add_workspace_argument, open_workspace, print_json


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    runs_parser = subparsers.add_parser(
        "runs",
        help="Inspect durable conversion runs.",
    )
    runs_subparsers = runs_parser.add_subparsers(dest="runs_command")

    runs_ls_parser = runs_subparsers.add_parser(
        "ls",
        help="List conversion runs.",
    )
    add_workspace_argument(runs_ls_parser)
    runs_ls_parser.set_defaults(handler=handle_list_runs)

    runs_show_parser = runs_subparsers.add_parser(
        "show",
        help="Show one conversion run.",
    )
    runs_show_parser.add_argument("run_id", help="Conversion run id.")
    add_workspace_argument(runs_show_parser)
    runs_show_parser.set_defaults(handler=handle_show_run)


def handle_list_runs(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    runs = workspace.list_conversion_runs()
    if not runs:
        print("No conversion runs.")
        return 0

    for run in runs:
        print(
            "\t".join(
                (
                    run.id,
                    run.status,
                    run.job_id or "-",
                    run.saved_config_id or "-",
                    run.output_dir,
                )
            )
        )
    return 0


def handle_show_run(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    run = workspace.get_conversion_run_or_raise(args.run_id)
    print_json(
        {
            "id": run.id,
            "job_id": run.job_id,
            "status": run.status,
            "source_asset_ids": run.source_asset_ids,
            "source_asset_paths": run.source_asset_paths,
            "saved_config_id": run.saved_config_id,
            "saved_config_revision_id": run.saved_config_revision_id,
            "config": run.config,
            "output_dir": run.output_dir,
            "output_paths": run.output_paths,
            "error_message": run.error_message,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
            "started_at": run.started_at.isoformat() if run.started_at is not None else None,
            "completed_at": (
                run.completed_at.isoformat() if run.completed_at is not None else None
            ),
        }
    )
    return 0
