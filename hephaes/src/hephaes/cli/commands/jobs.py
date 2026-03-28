from __future__ import annotations

import argparse

from ..common import add_workspace_argument, open_workspace, print_json


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    jobs_parser = subparsers.add_parser(
        "jobs",
        help="Inspect durable workspace jobs.",
    )
    jobs_subparsers = jobs_parser.add_subparsers(dest="jobs_command")

    jobs_ls_parser = jobs_subparsers.add_parser(
        "ls",
        help="List workspace jobs.",
    )
    add_workspace_argument(jobs_ls_parser)
    jobs_ls_parser.set_defaults(handler=handle_list_jobs)

    jobs_show_parser = jobs_subparsers.add_parser(
        "show",
        help="Show one workspace job.",
    )
    jobs_show_parser.add_argument("job_id", help="Workspace job id.")
    add_workspace_argument(jobs_show_parser)
    jobs_show_parser.set_defaults(handler=handle_show_job)


def handle_list_jobs(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    jobs = workspace.list_jobs()
    if not jobs:
        print("No jobs.")
        return 0

    for job in jobs:
        print(
            "\t".join(
                (
                    job.id,
                    job.kind,
                    job.status,
                    job.conversion_run_id or "-",
                    ",".join(job.target_asset_ids) or "-",
                )
            )
        )
    return 0


def handle_show_job(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    job = workspace.get_job_or_raise(args.job_id)
    print_json(
        {
            "id": job.id,
            "kind": job.kind,
            "status": job.status,
            "target_asset_ids": job.target_asset_ids,
            "config": job.config,
            "conversion_run_id": job.conversion_run_id,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at is not None else None,
            "completed_at": (
                job.completed_at.isoformat() if job.completed_at is not None else None
            ),
        }
    )
    return 0
