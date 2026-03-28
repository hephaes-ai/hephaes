from __future__ import annotations

import argparse

from ..common import add_workspace_argument, open_workspace


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    tags_parser = subparsers.add_parser(
        "tags",
        help="Manage asset tags in the active workspace.",
    )
    tags_subparsers = tags_parser.add_subparsers(dest="tags_command")

    tags_ls_parser = tags_subparsers.add_parser(
        "ls",
        help="List workspace tags.",
    )
    add_workspace_argument(tags_ls_parser)
    tags_ls_parser.set_defaults(handler=handle_list_tags)

    tags_create_parser = tags_subparsers.add_parser(
        "create",
        help="Create a new workspace tag.",
    )
    tags_create_parser.add_argument("name", help="Tag name.")
    add_workspace_argument(tags_create_parser)
    tags_create_parser.set_defaults(handler=handle_create_tag)

    tags_attach_parser = tags_subparsers.add_parser(
        "attach",
        help="Attach a tag to a registered asset.",
    )
    tags_attach_parser.add_argument("asset", help="Asset id or path.")
    tags_attach_parser.add_argument("tag", help="Tag id or name.")
    add_workspace_argument(tags_attach_parser)
    tags_attach_parser.set_defaults(handler=handle_attach_tag)

    tags_detach_parser = tags_subparsers.add_parser(
        "detach",
        help="Detach a tag from a registered asset.",
    )
    tags_detach_parser.add_argument("asset", help="Asset id or path.")
    tags_detach_parser.add_argument("tag", help="Tag id or name.")
    add_workspace_argument(tags_detach_parser)
    tags_detach_parser.set_defaults(handler=handle_detach_tag)


def handle_list_tags(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    tags = workspace.list_tags()
    if not tags:
        print("No tags defined.")
        return 0

    for tag in tags:
        print("\t".join((tag.id, tag.name)))
    return 0


def handle_create_tag(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    tag = workspace.create_tag(args.name)
    print("\t".join((tag.id, tag.name)))
    return 0


def handle_attach_tag(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    asset = workspace.resolve_asset(args.asset)
    tag = workspace.attach_tag_to_asset(args.asset, args.tag)
    print("\t".join((asset.id, tag.id, tag.name)))
    return 0


def handle_detach_tag(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    asset = workspace.resolve_asset(args.asset)
    tag = workspace.remove_tag_from_asset(args.asset, args.tag)
    print("\t".join((asset.id, tag.id, tag.name)))
    return 0
