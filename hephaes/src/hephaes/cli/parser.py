from __future__ import annotations

import argparse

from .. import __version__
from .commands import assets, configs, convert, inspect, jobs, outputs, runs, tags, workspace


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

    workspace.register(subparsers)
    assets.register(subparsers)
    tags.register(subparsers)
    inspect.register(subparsers)
    convert.register(subparsers)
    configs.register(subparsers)
    jobs.register(subparsers)
    runs.register(subparsers)
    outputs.register(subparsers)

    ls_parser = subparsers.add_parser(
        "ls",
        help="List workspace records.",
    )
    ls_subparsers = ls_parser.add_subparsers(dest="ls_command")
    assets.register_ls(ls_subparsers)

    return parser
