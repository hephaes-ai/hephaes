"""Thin indexing helpers reused by backend adapter routes and tests."""

from __future__ import annotations

from hephaes import Profiler
from hephaes.models import BagMetadata


def profile_asset_file(file_path: str) -> BagMetadata:
    """Profile a single asset file through the reusable hephaes package."""

    return Profiler([file_path], max_workers=1).profile()[0]
