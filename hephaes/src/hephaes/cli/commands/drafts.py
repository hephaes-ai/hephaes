from __future__ import annotations

import argparse

from ...conversion.draft_spec import DraftSpecRequest
from ...conversion.introspection import InspectionRequest
from ..common import add_workspace_argument, open_workspace, print_json


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    drafts_parser = subparsers.add_parser(
        "drafts",
        help="Manage conversion drafts in the active workspace.",
    )
    drafts_subparsers = drafts_parser.add_subparsers(dest="drafts_command")

    create_parser = drafts_subparsers.add_parser(
        "create",
        help="Inspect an asset and create a conversion draft.",
    )
    create_parser.add_argument("asset_selector", help="Registered asset id or path.")
    add_workspace_argument(create_parser)
    create_parser.add_argument("--label", help="Optional draft revision label.")
    _add_inspection_arguments(create_parser)
    _add_draft_request_arguments(create_parser)
    create_parser.set_defaults(handler=handle_create_draft)

    ls_parser = drafts_subparsers.add_parser(
        "ls",
        help="List conversion drafts.",
    )
    add_workspace_argument(ls_parser)
    ls_parser.add_argument(
        "--status",
        choices=("draft", "confirmed", "saved", "discarded"),
        help="Optional draft status filter.",
    )
    ls_parser.add_argument(
        "--asset",
        dest="asset_selector",
        help="Filter drafts by source asset selector.",
    )
    ls_parser.add_argument(
        "--config",
        dest="saved_config_selector",
        help="Filter drafts by saved config selector.",
    )
    ls_parser.set_defaults(handler=handle_list_drafts)

    show_parser = drafts_subparsers.add_parser(
        "show",
        help="Show one conversion draft.",
    )
    show_parser.add_argument("selector", help="Conversion draft id.")
    add_workspace_argument(show_parser)
    show_parser.set_defaults(handler=handle_show_draft)

    update_parser = drafts_subparsers.add_parser(
        "update",
        help="Append a new immutable revision to an existing draft.",
    )
    update_parser.add_argument("selector", help="Conversion draft id.")
    update_parser.add_argument(
        "--spec-document",
        required=True,
        help="Path to the updated conversion spec or conversion spec document.",
    )
    update_parser.add_argument("--label", help="Optional draft revision label.")
    add_workspace_argument(update_parser)
    update_parser.set_defaults(handler=handle_update_draft)

    preview_parser = drafts_subparsers.add_parser(
        "preview",
        help="Run preview for a draft revision and persist the result.",
    )
    preview_parser.add_argument("selector", help="Conversion draft id.")
    add_workspace_argument(preview_parser)
    preview_parser.add_argument(
        "--sample-n",
        type=int,
        default=5,
        help="Maximum number of preview rows to retain in the persisted preview snapshot.",
    )
    preview_parser.add_argument(
        "--revision",
        dest="revision_selector",
        help="Optional draft revision id. Defaults to the current draft revision.",
    )
    preview_parser.add_argument(
        "--type-hint",
        dest="type_hints",
        action="append",
        default=[],
        type=_parse_type_hint,
        metavar="TOPIC=TYPE",
        help="Override a topic type hint. Repeat for multiple hints.",
    )
    preview_parser.set_defaults(handler=handle_preview_draft)

    confirm_parser = drafts_subparsers.add_parser(
        "confirm",
        help="Confirm the current draft revision after preview.",
    )
    confirm_parser.add_argument("selector", help="Conversion draft id.")
    add_workspace_argument(confirm_parser)
    confirm_parser.add_argument(
        "--revision",
        dest="revision_selector",
        help="Optional draft revision id. Must match the current draft revision.",
    )
    confirm_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    confirm_parser.set_defaults(handler=handle_confirm_draft)

    discard_parser = drafts_subparsers.add_parser(
        "discard",
        help="Discard a draft while preserving its revision history.",
    )
    discard_parser.add_argument("selector", help="Conversion draft id.")
    add_workspace_argument(discard_parser)
    discard_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    discard_parser.set_defaults(handler=handle_discard_draft)

    save_config_parser = drafts_subparsers.add_parser(
        "save-config",
        help="Promote a confirmed draft into a reusable saved conversion config.",
    )
    save_config_parser.add_argument("selector", help="Conversion draft id.")
    add_workspace_argument(save_config_parser)
    save_config_parser.add_argument(
        "--name",
        required=True,
        help="Saved conversion config name.",
    )
    save_config_parser.add_argument(
        "--description",
        help="Optional saved conversion config description.",
    )
    save_config_parser.set_defaults(handler=handle_save_config_from_draft)


def _add_inspection_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--topic",
        dest="topics",
        action="append",
        default=[],
        help="Topic filter to inspect while creating the draft. Repeat for multiple topics.",
    )
    parser.add_argument(
        "--sample-n",
        type=int,
        default=8,
        help="Maximum number of sampled messages per topic during inspection.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=4,
        help="Maximum traversal depth for nested payload inspection.",
    )
    parser.add_argument(
        "--max-sequence-items",
        type=int,
        default=4,
        help="Maximum number of sequence items to inspect per message.",
    )
    parser.add_argument(
        "--on-failure",
        choices=("skip", "warn", "fail"),
        default="warn",
        help="Decode failure policy while sampling messages.",
    )


def _add_draft_request_arguments(parser: argparse.ArgumentParser) -> None:
    preview_group = parser.add_mutually_exclusive_group()
    preview_group.add_argument(
        "--include-preview",
        dest="include_preview",
        action="store_true",
        help="Generate an initial preview during draft creation.",
    )
    preview_group.add_argument(
        "--no-preview",
        dest="include_preview",
        action="store_false",
        help="Skip preview generation during draft creation.",
    )
    parser.set_defaults(include_preview=False)
    parser.add_argument("--trigger-topic", help="Explicit trigger topic for the draft request.")
    parser.add_argument(
        "--join-topic",
        dest="join_topics",
        action="append",
        default=[],
        help="Explicit join topic. Repeat for multiple topics.",
    )
    parser.add_argument(
        "--schema-name",
        default="draft_conversion",
        help="Schema name for the drafted conversion spec.",
    )
    parser.add_argument(
        "--schema-version",
        type=int,
        default=1,
        help="Schema version for the drafted conversion spec.",
    )
    parser.add_argument(
        "--output-format",
        choices=("parquet", "tfrecord"),
        default="tfrecord",
        help="Output format for the drafted conversion spec.",
    )
    parser.add_argument(
        "--output-compression",
        default="none",
        help="Output compression for the drafted conversion spec.",
    )
    parser.add_argument(
        "--max-features-per-topic",
        type=int,
        default=2,
        help="Maximum number of inferred features per selected topic.",
    )
    parser.add_argument(
        "--label-feature",
        help="Optional drafted feature name to treat as the primary label.",
    )
    parser.add_argument(
        "--preview-rows",
        type=int,
        default=5,
        help="Preview row count when --include-preview is enabled.",
    )


def _parse_type_hint(value: str) -> tuple[str, str]:
    topic, separator, type_hint = value.partition("=")
    topic = topic.strip()
    type_hint = type_hint.strip()
    if separator != "=" or not topic or not type_hint:
        raise argparse.ArgumentTypeError(
            "type hints must use TOPIC=TYPE syntax, for example /camera=sensor_msgs/msg/Image"
        )
    return topic, type_hint


def _build_inspection_request(args: argparse.Namespace) -> InspectionRequest:
    return InspectionRequest(
        topics=args.topics or [],
        sample_n=args.sample_n,
        max_depth=args.max_depth,
        max_sequence_items=args.max_sequence_items,
        on_failure=args.on_failure,
    )


def _build_draft_request(args: argparse.Namespace) -> DraftSpecRequest:
    return DraftSpecRequest(
        trigger_topic=args.trigger_topic,
        selected_topics=args.topics or [],
        join_topics=args.join_topics or [],
        schema_name=args.schema_name,
        schema_version=args.schema_version,
        output_format=args.output_format,
        output_compression=args.output_compression,
        max_features_per_topic=args.max_features_per_topic,
        label_feature=args.label_feature,
        include_preview=args.include_preview,
        preview_rows=args.preview_rows,
    )


def _type_hints_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {topic: type_hint for topic, type_hint in args.type_hints}


def _serialize_timestamp(value) -> str | None:
    return value.isoformat() if value is not None else None


def _serialize_draft_revision(revision, *, include_document: bool) -> dict:
    payload = {
        "id": revision.id,
        "draft_id": revision.draft_id,
        "revision_number": revision.revision_number,
        "label": revision.label,
        "saved_config_id": revision.saved_config_id,
        "source_asset_id": revision.source_asset_id,
        "status": revision.status,
        "metadata": revision.metadata,
        "inspection_request": revision.inspection_request_json,
        "inspection": revision.inspection_json,
        "draft_request": revision.draft_request_json,
        "draft_result": revision.draft_result_json,
        "preview_request": revision.preview_request_json,
        "preview": revision.preview_json,
        "spec_document_version": revision.spec_document_version,
        "document_path": revision.document_path,
        "created_at": _serialize_timestamp(revision.created_at),
        "updated_at": _serialize_timestamp(revision.updated_at),
        "invalid_reason": revision.invalid_reason,
    }
    if include_document:
        payload["document"] = revision.document.model_dump(mode="json")
    return payload


def _serialize_draft_revision_summary(summary) -> dict:
    return {
        "id": summary.id,
        "draft_id": summary.draft_id,
        "revision_number": summary.revision_number,
        "label": summary.label,
        "saved_config_id": summary.saved_config_id,
        "source_asset_id": summary.source_asset_id,
        "status": summary.status,
        "metadata": summary.metadata,
        "inspection_request": summary.inspection_request_json,
        "inspection": summary.inspection_json,
        "draft_request": summary.draft_request_json,
        "draft_result": summary.draft_result_json,
        "preview_request": summary.preview_request_json,
        "preview": summary.preview_json,
        "spec_document_version": summary.spec_document_version,
        "document_path": summary.document_path,
        "created_at": _serialize_timestamp(summary.created_at),
        "updated_at": _serialize_timestamp(summary.updated_at),
        "invalid_reason": summary.invalid_reason,
    }


def _serialize_draft(draft, *, revision_summaries=None) -> dict:
    payload = {
        "id": draft.id,
        "source_asset_id": draft.source_asset_id,
        "status": draft.status,
        "current_revision_id": draft.current_revision_id,
        "confirmed_revision_id": draft.confirmed_revision_id,
        "saved_config_id": draft.saved_config_id,
        "created_at": _serialize_timestamp(draft.created_at),
        "updated_at": _serialize_timestamp(draft.updated_at),
        "discarded_at": _serialize_timestamp(draft.discarded_at),
        "current_revision": (
            _serialize_draft_revision(draft.current_revision, include_document=True)
            if draft.current_revision is not None
            else None
        ),
        "confirmed_revision": (
            _serialize_draft_revision(draft.confirmed_revision, include_document=True)
            if draft.confirmed_revision is not None
            else None
        ),
    }
    if revision_summaries is not None:
        payload["revisions"] = [
            _serialize_draft_revision_summary(revision)
            for revision in revision_summaries
        ]
    return payload


def _serialize_saved_config(config) -> dict:
    return {
        "id": config.id,
        "name": config.name,
        "description": config.description,
        "metadata": config.metadata,
        "spec_document_version": config.spec_document_version,
        "document_path": config.document_path,
        "created_at": _serialize_timestamp(config.created_at),
        "updated_at": _serialize_timestamp(config.updated_at),
        "last_opened_at": _serialize_timestamp(config.last_opened_at),
        "invalid_reason": config.invalid_reason,
        "document": config.document.model_dump(mode="json"),
    }


def _confirm_or_abort(prompt: str, *, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    answer = input(f"{prompt} [y/N]: ").strip().casefold()
    return answer in {"y", "yes"}


def handle_create_draft(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    draft = workspace.create_conversion_draft(
        args.asset_selector,
        inspection_request=_build_inspection_request(args),
        draft_request=_build_draft_request(args),
        label=args.label,
    )
    print_json(_serialize_draft(draft))
    return 0


def handle_list_drafts(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    drafts = workspace.list_conversion_drafts(
        status=args.status,
        source_asset_selector=args.asset_selector,
        saved_config_selector=args.saved_config_selector,
    )
    if not drafts:
        print("No conversion drafts.")
        return 0

    for draft in drafts:
        print(
            "\t".join(
                (
                    draft.id,
                    draft.status,
                    draft.source_asset_id or "-",
                    draft.current_revision_id or "-",
                    draft.saved_config_id or "-",
                )
            )
        )
    return 0


def handle_show_draft(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    draft = workspace.resolve_conversion_draft(args.selector)
    revisions = workspace.list_conversion_draft_revisions(draft_selector=draft.id)
    print_json(_serialize_draft(draft, revision_summaries=revisions))
    return 0


def handle_update_draft(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    draft = workspace.update_conversion_draft(
        args.selector,
        spec_document=args.spec_document,
        label=args.label,
    )
    print_json(_serialize_draft(draft))
    return 0


def handle_preview_draft(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    draft = workspace.preview_conversion_draft(
        args.selector,
        sample_n=args.sample_n,
        topic_type_hints=_type_hints_from_args(args) or None,
        revision_selector=args.revision_selector,
    )
    print_json(_serialize_draft(draft))
    return 0


def handle_confirm_draft(args: argparse.Namespace) -> int:
    if not _confirm_or_abort(
        f"Confirm draft {args.selector}?",
        assume_yes=args.yes,
    ):
        print("Confirmation aborted.")
        return 1

    workspace = open_workspace(args.workspace)
    draft = workspace.confirm_conversion_draft(
        args.selector,
        revision_selector=args.revision_selector,
    )
    print_json(_serialize_draft(draft))
    return 0


def handle_discard_draft(args: argparse.Namespace) -> int:
    if not _confirm_or_abort(
        f"Discard draft {args.selector}?",
        assume_yes=args.yes,
    ):
        print("Discard aborted.")
        return 1

    workspace = open_workspace(args.workspace)
    draft = workspace.discard_conversion_draft(args.selector)
    print_json(_serialize_draft(draft))
    return 0


def handle_save_config_from_draft(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    config = workspace.save_conversion_config_from_draft(
        args.selector,
        name=args.name,
        description=args.description,
    )
    print_json(_serialize_saved_config(config))
    return 0
