from __future__ import annotations

import argparse

from ..common import add_workspace_argument, print_json, resolve_inspect_path


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect the structure of a local asset.",
    )
    inspect_parser.add_argument(
        "selector",
        help="Registered asset id, registered asset path, or direct local file path.",
    )
    add_workspace_argument(inspect_parser)
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
    inspect_parser.set_defaults(handler=handle_inspect)


def handle_inspect(args: argparse.Namespace) -> int:
    from .. import inspect_bag

    bag_path = resolve_inspect_path(args.selector, args.workspace)
    inspection = inspect_bag(
        bag_path,
        topics=args.topics or None,
        sample_n=args.sample_n,
        max_depth=args.max_depth,
        max_sequence_items=args.max_sequence_items,
        on_failure=args.on_failure,
    )
    print_json(inspection.model_dump(mode="json"))
    return 0
