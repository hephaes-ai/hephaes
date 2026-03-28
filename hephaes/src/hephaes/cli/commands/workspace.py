from __future__ import annotations

import argparse

from ...workspace import Workspace


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
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
    init_parser.set_defaults(handler=handle_init)


def handle_init(args: argparse.Namespace) -> int:
    workspace = Workspace.init(args.path, exist_ok=args.exist_ok)
    print(f"Initialized Hephaes workspace at {workspace.workspace_dir}")
    return 0
