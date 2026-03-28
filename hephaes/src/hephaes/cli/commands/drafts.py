from __future__ import annotations

import argparse

from ...conversion.draft_spec import DraftSpecRequest
from ...conversion.introspection import InspectionRequest
from ..common import add_workspace_argument, open_workspace, print_json
from ...workspace import WorkspaceError


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

    wizard_parser = drafts_subparsers.add_parser(
        "wizard",
        help="Run the interactive conversion draft wizard.",
    )
    wizard_parser.add_argument(
        "asset_selector",
        nargs="?",
        help="Registered asset id or path to start a new wizard draft from.",
    )
    add_workspace_argument(wizard_parser)
    wizard_parser.add_argument(
        "--draft",
        dest="draft_selector",
        help="Existing draft id to resume instead of creating a new draft.",
    )
    wizard_parser.set_defaults(handler=handle_draft_wizard)


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


def _prompt_text(
    prompt: str,
    *,
    default: str | None = None,
    allow_empty: bool = False,
) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        if allow_empty:
            return ""
        print("Value required.")


def _prompt_int(prompt: str, *, default: int, minimum: int = 1) -> int:
    while True:
        raw = _prompt_text(prompt, default=str(default))
        try:
            value = int(raw)
        except ValueError:
            print("Enter a whole number.")
            continue
        if value < minimum:
            print(f"Enter a value >= {minimum}.")
            continue
        return value


def _prompt_yes_no(prompt: str, *, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{suffix}]: ").strip().casefold()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def _prompt_wizard_inspection_request() -> InspectionRequest:
    sample_n = _prompt_int("Inspection sample count", default=8, minimum=1)
    topics_text = _prompt_text(
        "Inspection topics (comma-separated, blank for all)",
        default="",
        allow_empty=True,
    )
    topics = [topic.strip() for topic in topics_text.split(",") if topic.strip()]
    return InspectionRequest(
        topics=topics,
        sample_n=sample_n,
    )


def _prompt_wizard_draft_request(inspection_request: InspectionRequest) -> DraftSpecRequest:
    trigger_topic = _prompt_text(
        "Trigger topic (blank for auto)",
        default="",
        allow_empty=True,
    )
    max_features = _prompt_int("Max features per topic", default=2, minimum=1)
    label_feature = _prompt_text(
        "Primary label feature (blank for none)",
        default="",
        allow_empty=True,
    )
    while True:
        output_format = _prompt_text("Output format", default="tfrecord").casefold()
        if output_format in {"tfrecord", "parquet"}:
            break
        print("Output format must be 'tfrecord' or 'parquet'.")
    return DraftSpecRequest(
        trigger_topic=trigger_topic or None,
        selected_topics=inspection_request.topics,
        schema_name="draft_conversion",
        schema_version=1,
        output_format=output_format,
        output_compression="none",
        max_features_per_topic=max_features,
        label_feature=label_feature or None,
        include_preview=False,
        preview_rows=5,
    )


def _available_wizard_actions(status: str) -> list[str]:
    if status == "draft":
        return ["show", "update", "preview", "confirm", "save", "discard", "exit"]
    if status == "confirmed":
        return ["show", "update", "preview", "save", "discard", "exit"]
    return ["show", "exit"]


def _prompt_wizard_action(status: str) -> str:
    actions = _available_wizard_actions(status)
    return _prompt_text(
        f"Wizard action ({', '.join(actions)})",
        default="show" if status in {"saved", "discarded"} else "preview",
    ).casefold()


def _print_preview_summary(draft) -> None:
    current_revision = draft.current_revision
    if current_revision is None or current_revision.preview_json is None:
        print("No preview has been recorded for the current revision.")
        return
    preview = current_revision.preview_json
    print(
        "Preview rows="
        f"{len(preview.get('rows', []))} checked={preview.get('checked_records', 0)} "
        f"bad={preview.get('bad_records', 0)}"
    )


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


def handle_draft_wizard(args: argparse.Namespace) -> int:
    workspace = open_workspace(args.workspace)
    if args.draft_selector and args.asset_selector:
        print("Choose either an asset selector or --draft, not both.")
        return 1
    if not args.draft_selector and not args.asset_selector:
        print("Provide an asset selector or --draft to run the wizard.")
        return 1

    if args.draft_selector:
        draft = workspace.resolve_conversion_draft(args.draft_selector)
        print(f"Resuming draft {draft.id} (status={draft.status}).")
    else:
        inspection_request = _prompt_wizard_inspection_request()
        draft_request = _prompt_wizard_draft_request(inspection_request)
        draft = workspace.create_conversion_draft(
            args.asset_selector,
            inspection_request=inspection_request,
            draft_request=draft_request,
            label="Wizard Draft",
        )
        print(f"Created draft {draft.id}.")

    while True:
        draft = workspace.resolve_conversion_draft(draft.id)
        print(
            f"Draft {draft.id} status={draft.status} "
            f"current_revision={draft.current_revision_id or '-'}"
        )
        action = _prompt_wizard_action(draft.status)
        if action not in _available_wizard_actions(draft.status):
            print(f"Unknown action: {action}")
            continue

        if action == "show":
            revisions = workspace.list_conversion_draft_revisions(draft_selector=draft.id)
            print_json(_serialize_draft(draft, revision_summaries=revisions))
            if draft.status in {"saved", "discarded"}:
                return 0
            continue

        if action == "exit":
            print_json(_serialize_draft(draft))
            return 0

        try:
            if action == "update":
                spec_document = _prompt_text("Edited spec document path")
                label = _prompt_text(
                    "Revision label (blank for none)",
                    default="",
                    allow_empty=True,
                )
                draft = workspace.update_conversion_draft(
                    draft.id,
                    spec_document=spec_document,
                    label=label or None,
                )
                print(f"Draft {draft.id} updated to revision {draft.current_revision_id}.")
                continue

            if action == "preview":
                sample_n = _prompt_int("Preview row count", default=5, minimum=1)
                draft = workspace.preview_conversion_draft(draft.id, sample_n=sample_n)
                _print_preview_summary(draft)
                continue

            if action == "confirm":
                draft = workspace.confirm_conversion_draft(draft.id)
                print(f"Draft {draft.id} confirmed.")
                continue

            if action == "save":
                name = _prompt_text("Saved config name")
                description = _prompt_text(
                    "Saved config description (blank for none)",
                    default="",
                    allow_empty=True,
                )
                config = workspace.save_conversion_config_from_draft(
                    draft.id,
                    name=name,
                    description=description or None,
                )
                print_json(_serialize_saved_config(config))
                return 0

            if action == "discard":
                if not _prompt_yes_no("Discard this draft?", default=False):
                    print("Discard aborted.")
                    continue
                draft = workspace.discard_conversion_draft(draft.id)
                print_json(_serialize_draft(draft))
                return 0
        except WorkspaceError as exc:
            print(f"Error: {exc}")
