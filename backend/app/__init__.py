"""FastAPI application package."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_repo_hephaes_src() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    hephaes_src_dir = repo_root / "hephaes" / "src"

    if not hephaes_src_dir.is_dir():
        return

    resolved_path = str(hephaes_src_dir)
    if resolved_path not in sys.path:
        sys.path.insert(0, resolved_path)


_bootstrap_repo_hephaes_src()
