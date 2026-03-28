from __future__ import annotations

from .assets import WorkspaceAssetMixin
from .configs import WorkspaceConfigMixin
from .conversions import WorkspaceConversionMixin
from .core import WorkspaceCoreMixin
from .drafts import WorkspaceDraftMixin
from .jobs import WorkspaceJobMixin
from .outputs import WorkspaceOutputMixin
from .tags import WorkspaceTagMixin


class Workspace(
    WorkspaceConversionMixin,
    WorkspaceOutputMixin,
    WorkspaceJobMixin,
    WorkspaceDraftMixin,
    WorkspaceConfigMixin,
    WorkspaceTagMixin,
    WorkspaceAssetMixin,
    WorkspaceCoreMixin,
):
    """Package-owned local workspace for persistent Hephaes state."""

