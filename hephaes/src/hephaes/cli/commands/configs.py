from __future__ import annotations

import argparse

from ..common import add_workspace_argument, open_workspace, print_json


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    configs_parser = subparsers.add_parser(
        "configs",
        help="Manage saved conversion configs in the active workspace.",
    )
    configs_subparsers = configs_parser.add_subparsers(dest="configs_command")

    configs_ls_parser = configs_subparsers.add_parser(
        "ls",
        help="List saved conversion configs.",
    )
    add_workspace_argument(configs_ls_parser)
    configs_ls_parser.set_defaults(handler=handle_list_configs)

    configs_show_parser = configs_subparsers.add_parser(
        "show",
        help="Show one saved conversion config.",
    )
    configs_show_parser.add_argument("selector", help="Saved config id or name.")
    add_workspace_argument(configs_show_parser)
    configs_show_parser.set_defaults(handler=handle_show_config)

    configs_save_parser = configs_subparsers.add_parser(
        "save",
        help="Save a conversion spec document into the workspace config store.",
    )
    configs_save_parser.add_argument("name", help="Saved config name.")
    configs_save_parser.add_argument(
        "spec_document",
        help="Path to a conversion spec or conversion spec document.",
    )
    add_workspace_argument(configs_save_parser)
    configs_save_parser.add_argument(
        "--description",
        help="Optional saved config description.",
    )
    configs_save_parser.set_defaults(handler=handle_save_config)

    configs_update_parser = configs_subparsers.add_parser(
        "update",
        help="Replace a saved conversion config document and record a new revision.",
    )
    configs_update_parser.add_argument("selector", help="Saved config id or name.")
    configs_update_parser.add_argument(
        "spec_document",
        help="Path to a conversion spec or conversion spec document.",
    )
    add_workspace_argument(configs_update_parser)
    configs_update_parser.add_argument(
        "--name",
        help="Optional new display name for the saved config.",
    )
    configs_update_parser.add_argument(
        "--description",
        help="Optional updated description.",
    )
    configs_update_parser.set_defaults(handler=handle_update_config)

    configs_duplicate_parser = configs_subparsers.add_parser(
        "duplicate",
        help="Duplicate a saved conversion config under a new name.",
    )
    configs_duplicate_parser.add_argument("selector", help="Saved config id or name.")
    configs_duplicate_parser.add_argument("name", help="Name for the duplicated config.")
    add_workspace_argument(configs_duplicate_parser)
    configs_duplicate_parser.add_argument(
        "--description",
        help="Optional description for the duplicated config.",
    )
    configs_duplicate_parser.set_defaults(handler=handle_duplicate_config)

    configs_revisions_parser = configs_subparsers.add_parser(
        "revisions",
        help="List saved conversion config revisions.",
    )
    configs_revisions_parser.add_argument("selector", help="Saved config id or name.")
    add_workspace_argument(configs_revisions_parser)
    configs_revisions_parser.set_defaults(handler=handle_list_config_revisions)


def handle_list_configs(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
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


def handle_show_config(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    config = workspace.resolve_saved_conversion_config(args.selector)
    revisions = workspace.list_saved_conversion_config_revisions(config.id)
    print_json(
        {
            "id": config.id,
            "name": config.name,
            "description": config.description,
            "metadata": config.metadata,
            "spec_document_version": config.spec_document_version,
            "document_path": config.document_path,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat(),
            "last_opened_at": (
                config.last_opened_at.isoformat() if config.last_opened_at is not None else None
            ),
            "invalid_reason": config.invalid_reason,
            "revision_count": len(revisions),
            "current_schema": {
                "name": config.document.spec.schema.name,
                "version": config.document.spec.schema.version,
            },
        }
    )
    return 0


def _print_saved_config_summary(config) -> None:
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


def handle_save_config(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    config = workspace.save_conversion_config(
        name=args.name,
        spec_document=args.spec_document,
        description=args.description,
    )
    _print_saved_config_summary(config)
    return 0


def handle_update_config(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    config = workspace.update_saved_conversion_config(
        args.selector,
        spec_document=args.spec_document,
        name=args.name,
        description=args.description,
    )
    _print_saved_config_summary(config)
    return 0


def handle_duplicate_config(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    config = workspace.duplicate_saved_conversion_config(
        args.selector,
        name=args.name,
        description=args.description,
    )
    _print_saved_config_summary(config)
    return 0


def handle_list_config_revisions(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    revisions = workspace.list_saved_conversion_config_revisions(args.selector)
    if not revisions:
        print("No saved conversion config revisions.")
        return 0

    for revision in revisions:
        print(
            "\t".join(
                (
                    revision.id,
                    revision.config_id,
                    str(revision.revision_number),
                    str(revision.spec_document_version),
                    revision.document_path,
                )
            )
        )
    return 0
