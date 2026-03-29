from __future__ import annotations


class WorkspaceError(Exception):
    """Base exception for workspace operations."""


class WorkspaceNotFoundError(WorkspaceError):
    """Raised when no workspace can be resolved for the requested path."""


class WorkspaceAlreadyExistsError(WorkspaceError):
    """Raised when attempting to initialize an existing workspace."""


class UnsupportedWorkspaceSchemaError(WorkspaceError):
    """Raised when a workspace database uses an unsupported schema version."""


class InvalidAssetPathError(WorkspaceError):
    """Raised when a requested asset path does not point to a supported local file."""


class AssetAlreadyRegisteredError(WorkspaceError):
    """Raised when a requested asset path already exists in the workspace."""


class AssetNotFoundError(WorkspaceError):
    """Raised when a requested asset cannot be found in the workspace."""


class AssetUnavailableError(WorkspaceError):
    """Raised when a registered asset path no longer points to a usable local file."""


class AssetReadError(WorkspaceError):
    """Raised when a workspace asset cannot be opened or read for authoring."""


class TagAlreadyExistsError(WorkspaceError):
    """Raised when a tag with the requested name already exists."""


class TagNotFoundError(WorkspaceError):
    """Raised when a requested tag cannot be found in the workspace."""


class ConversionConfigAlreadyExistsError(WorkspaceError):
    """Raised when a saved conversion config name already exists."""


class ConversionConfigNotFoundError(WorkspaceError):
    """Raised when a saved conversion config cannot be found."""


class ConversionConfigInvalidError(WorkspaceError):
    """Raised when a saved conversion config document cannot be loaded."""


class ConversionDraftNotFoundError(WorkspaceError):
    """Raised when a conversion draft cannot be found."""


class ConversionDraftRevisionNotFoundError(WorkspaceError):
    """Raised when a conversion draft revision cannot be found."""


class ConversionDraftStateError(WorkspaceError):
    """Raised when a conversion draft cannot perform the requested state transition."""


class ConversionDraftConfirmationError(WorkspaceError):
    """Raised when a draft cannot be confirmed because required conditions are unmet."""


class OutputArtifactNotFoundError(WorkspaceError):
    """Raised when a tracked output artifact cannot be found."""
