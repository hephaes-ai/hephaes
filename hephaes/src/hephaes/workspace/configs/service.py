from __future__ import annotations

from .documents import WorkspaceConfigDocumentMixin
from .mutations import WorkspaceConfigMutationMixin
from .queries import WorkspaceConfigQueryMixin
from .revisions import WorkspaceConfigRevisionMixin


class WorkspaceConfigMixin(
    WorkspaceConfigMutationMixin,
    WorkspaceConfigQueryMixin,
    WorkspaceConfigDocumentMixin,
    WorkspaceConfigRevisionMixin,
):
    """Saved conversion config workspace APIs."""
