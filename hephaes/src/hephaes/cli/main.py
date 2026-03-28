from __future__ import annotations

import sys
from typing import Sequence

from ..workspace import (
    AssetAlreadyRegisteredError,
    ConversionConfigAlreadyExistsError,
    InvalidAssetPathError,
    OutputArtifactNotFoundError,
    TagAlreadyExistsError,
    TagNotFoundError,
    WorkspaceError,
)
from .parser import build_parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help(sys.stderr)
        return 1

    try:
        return int(handler(args))
    except (
        WorkspaceError,
        InvalidAssetPathError,
        AssetAlreadyRegisteredError,
        ConversionConfigAlreadyExistsError,
        OutputArtifactNotFoundError,
        TagAlreadyExistsError,
        TagNotFoundError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def entrypoint() -> None:
    raise SystemExit(main())
