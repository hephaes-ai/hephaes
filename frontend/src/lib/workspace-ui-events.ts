"use client"

export type WorkspaceCreateIntent = "create" | "open"

type WorkspaceUiRequest =
  | { type: "open-manage" }
  | { intent: WorkspaceCreateIntent; type: "open-create" }

const WORKSPACE_UI_REQUEST_EVENT = "hephaes:workspace-ui-request"

function dispatchWorkspaceUiRequest(request: WorkspaceUiRequest) {
  if (typeof window === "undefined") {
    return
  }

  window.dispatchEvent(
    new CustomEvent<WorkspaceUiRequest>(WORKSPACE_UI_REQUEST_EVENT, {
      detail: request,
    })
  )
}

export function requestOpenManageWorkspaces() {
  dispatchWorkspaceUiRequest({ type: "open-manage" })
}

export function requestOpenCreateWorkspace(
  intent: WorkspaceCreateIntent = "create"
) {
  dispatchWorkspaceUiRequest({ intent, type: "open-create" })
}

export function subscribeToWorkspaceUiRequests(
  listener: (request: WorkspaceUiRequest) => void
) {
  if (typeof window === "undefined") {
    return () => {}
  }

  const handleEvent = (event: Event) => {
    const customEvent = event as CustomEvent<WorkspaceUiRequest>
    if (!customEvent.detail) {
      return
    }

    listener(customEvent.detail)
  }

  window.addEventListener(WORKSPACE_UI_REQUEST_EVENT, handleEvent)

  return () => {
    window.removeEventListener(WORKSPACE_UI_REQUEST_EVENT, handleEvent)
  }
}
