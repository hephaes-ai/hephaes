"""Service helpers for registering and retrieving local assets."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SUPPORTED_ASSET_FILE_TYPES = {"bag", "mcap"}


class AssetServiceError(Exception):
    """Base exception for asset service failures."""


class InvalidAssetPathError(AssetServiceError):
    """Raised when a requested asset path is invalid or unusable."""


class AssetDialogUnavailableError(AssetServiceError):
    """Raised when the local environment cannot open a native file picker."""


class AssetNotFoundError(AssetServiceError):
    """Raised when an asset cannot be found in the registry."""


class InvalidAssetUploadError(AssetServiceError):
    """Raised when an uploaded file is invalid or unsupported."""


class EpisodeDiscoveryUnavailableError(AssetServiceError):
    """Raised when episode summaries are not available for an asset."""


@dataclass(frozen=True)
class AssetRegistrationSkip:
    """Reason a selected file could not be added to the registry."""

    detail: str
    file_path: str
    reason: str


@dataclass(frozen=True)
class AssetEpisodeSummary:
    """Episode summary derived from indexed asset metadata."""

    default_lane_count: int
    duration: float
    end_time: datetime | None
    episode_id: str
    has_visualizable_streams: bool
    label: str
    start_time: datetime | None


TK_FILE_DIALOG_SCRIPT = """
import json
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
root.update_idletasks()

try:
    root.attributes("-topmost", True)
except Exception:
    pass

paths = filedialog.askopenfilenames(
    title="Choose asset files",
    filetypes=[
        ("ROS logs", "*.bag *.mcap"),
        ("MCAP files", "*.mcap"),
        ("ROS bag files", "*.bag"),
        ("All files", "*.*"),
    ],
)

print(json.dumps(list(paths)))
root.destroy()
"""

MACOS_FILE_DIALOG_SCRIPT = """
try
    set chosenFiles to choose file with prompt "Choose asset files" of type {"bag", "mcap"} multiple selections allowed true
on error number -128
    return ""
end try

if class of chosenFiles is alias then
    set chosenFiles to {chosenFiles}
end if

set outputLines to {}
repeat with chosenFile in chosenFiles
    set end of outputLines to POSIX path of chosenFile
end repeat

set AppleScript's text item delimiters to linefeed
return outputLines as text
"""


def normalize_asset_path(file_path: str) -> Path:
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = path.resolve(strict=False)
    else:
        path = path.resolve(strict=False)
    return path


def infer_file_type(path: Path) -> str:
    suffix = path.suffix.strip().lower()
    if suffix.startswith("."):
        suffix = suffix[1:]
    return suffix or "unknown"


def _validate_supported_file_type(file_name: str) -> str:
    file_type = infer_file_type(Path(file_name))
    if file_type not in SUPPORTED_ASSET_FILE_TYPES:
        supported_types = ", ".join(sorted(SUPPORTED_ASSET_FILE_TYPES))
        raise InvalidAssetUploadError(
            f"unsupported asset type: {file_name} (supported: {supported_types})"
        )
    return file_type


def normalize_uploaded_file_name(file_name: str) -> str:
    trimmed = file_name.strip()
    if not trimmed:
        raise InvalidAssetUploadError("uploaded file name must be non-empty")

    normalized_name = Path(trimmed).name
    if normalized_name in {"", ".", ".."}:
        raise InvalidAssetUploadError("uploaded file name is invalid")

    _validate_supported_file_type(normalized_name)
    return normalized_name


def _iter_supported_asset_files(directory: Path, *, recursive: bool) -> Iterable[Path]:
    candidates = directory.rglob("*") if recursive else directory.iterdir()
    for candidate in sorted(candidates):
        if not candidate.is_file():
            continue
        if infer_file_type(candidate) not in SUPPORTED_ASSET_FILE_TYPES:
            continue
        yield candidate


def _parse_dialog_output(stdout: str) -> list[str]:
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def _run_dialog_command(command: list[str], *, input_text: str | None = None) -> list[str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            input=input_text,
            text=True,
        )
    except OSError as exc:
        raise AssetDialogUnavailableError("native file picker could not be started") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        message = stderr or "native file picker is unavailable in this environment"
        raise AssetDialogUnavailableError(message)

    return _parse_dialog_output(completed.stdout)


def _open_asset_file_dialog_with_tk() -> list[str]:
    selected_paths = _run_dialog_command(
        [sys.executable, "-c", TK_FILE_DIALOG_SCRIPT],
    )
    if not selected_paths:
        return []

    try:
        parsed_paths = json.loads("\n".join(selected_paths))
    except json.JSONDecodeError as exc:
        raise AssetDialogUnavailableError("native file picker returned an invalid response") from exc

    if not isinstance(parsed_paths, list):
        raise AssetDialogUnavailableError("native file picker returned an unexpected payload")

    return [str(path) for path in parsed_paths if isinstance(path, str) and path.strip()]


def _open_asset_file_dialog_with_osascript() -> list[str]:
    if shutil.which("osascript") is None:
        raise AssetDialogUnavailableError("osascript is not available")

    return _run_dialog_command(
        ["osascript", "-"],
        input_text=MACOS_FILE_DIALOG_SCRIPT,
    )


def open_asset_file_dialog() -> list[str]:
    picker_attempts = []

    if sys.platform == "darwin":
        picker_attempts.append(_open_asset_file_dialog_with_osascript)

    picker_attempts.append(_open_asset_file_dialog_with_tk)

    last_error: AssetDialogUnavailableError | None = None
    for picker_attempt in picker_attempts:
        try:
            return picker_attempt()
        except AssetDialogUnavailableError as exc:
            last_error = exc

    raise last_error or AssetDialogUnavailableError(
        "native file picker is unavailable in this environment"
    )
