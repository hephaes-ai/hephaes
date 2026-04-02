"use client"

import * as React from "react"
import {
  CheckCircle2,
  ChevronDown,
  FolderOpen,
  LoaderCircle,
  Plus,
} from "lucide-react"

import { InlineNotice } from "@/components/inline-notice"
import { useFeedback } from "@/components/feedback-provider"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useWorkspace } from "@/components/workspace-provider"
import { useFrontendRuntime } from "@/hooks/use-desktop-backend-runtime"
import { openDirectoryDialog } from "@/lib/native-dialogs"
import type { WorkspaceRegistrySummary } from "@/lib/api"
import type { NoticeMessage } from "@/lib/types"

interface CreateWorkspaceDraft {
  name: string
  rootPath: string
}

const EMPTY_DRAFT: CreateWorkspaceDraft = {
  name: "",
  rootPath: "",
}

function deriveWorkspaceName(rootPath: string) {
  const normalizedPath = rootPath.trim().replace(/[\\/]+$/, "")
  if (!normalizedPath) {
    return ""
  }

  const segments = normalizedPath.split(/[\\/]+/)
  return segments.at(-1) ?? normalizedPath
}

function getWorkspaceStatusLabel(workspace: WorkspaceRegistrySummary) {
  switch (workspace.status) {
    case "invalid":
      return "Invalid"
    case "missing":
      return "Missing"
    default:
      return "Ready"
  }
}

function getWorkspaceStatusVariant(workspace: WorkspaceRegistrySummary) {
  return workspace.status === "ready" ? "outline" : "destructive"
}

export function WorkspaceSwitcher() {
  const workspace = useWorkspace()
  const runtime = useFrontendRuntime()
  const { notify } = useFeedback()
  const [isDropdownOpen, setIsDropdownOpen] = React.useState(false)
  const [isManageDialogOpen, setIsManageDialogOpen] = React.useState(false)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = React.useState(false)
  const [createDraft, setCreateDraft] =
    React.useState<CreateWorkspaceDraft>(EMPTY_DRAFT)
  const [createNotice, setCreateNotice] = React.useState<NoticeMessage | null>(
    null
  )
  const canBrowseDirectories =
    runtime?.capabilities.nativeDirectoryDialog ?? false

  function resetCreateDialog() {
    setCreateDraft(EMPTY_DRAFT)
    setCreateNotice(null)
  }

  function handleCreateDialogOpenChange(open: boolean) {
    if (!open && workspace.isCreatingWorkspace) {
      return
    }

    setIsCreateDialogOpen(open)
    if (!open) {
      resetCreateDialog()
    }
  }

  async function beginCreateWorkspaceFlow() {
    if (workspace.isCreatingWorkspace) {
      return false
    }

    if (!canBrowseDirectories) {
      notify({
        description:
          "This runtime cannot open the native directory picker yet.",
        title: "Directory picker unavailable",
        tone: "error",
      })
      return false
    }

    const selection = await openDirectoryDialog()

    if (selection.status === "cancelled") {
      return false
    }

    if (selection.status === "error") {
      notify({
        description: selection.error,
        title: "Directory picker unavailable",
        tone: "error",
      })
      return false
    }

    setCreateDraft({
      name: deriveWorkspaceName(selection.directoryPath),
      rootPath: selection.directoryPath,
    })
    setCreateNotice(null)
    setIsCreateDialogOpen(true)
    return true
  }

  async function handleActivateWorkspace(workspaceId: string) {
    if (
      workspace.activatingWorkspaceId ||
      workspaceId === workspace.activeWorkspaceId
    ) {
      return
    }

    try {
      await workspace.setActiveWorkspace(workspaceId)
      notify({
        description: "The selected workspace is now active.",
        title: "Workspace switched",
        tone: "success",
      })
    } catch (error) {
      notify({
        description:
          error instanceof Error
            ? error.message
            : "The workspace could not be activated.",
        title: "Could not switch workspace",
        tone: "error",
      })
    }
  }

  async function handleCreateWorkspace(
    event: React.FormEvent<HTMLFormElement>
  ) {
    event.preventDefault()

    const normalizedRootPath = createDraft.rootPath.trim()
    const normalizedName = createDraft.name.trim()

    if (!normalizedRootPath) {
      setCreateNotice({
        description: "Choose a working directory before creating a workspace.",
        title: "Directory required",
        tone: "error",
      })
      return
    }

    if (!normalizedName) {
      setCreateNotice({
        description: "Enter a display name for the workspace.",
        title: "Workspace name required",
        tone: "error",
      })
      return
    }

    setCreateNotice(null)

    try {
      const createdWorkspace = await workspace.createWorkspace({
        activate: true,
        name: normalizedName,
        root_path: normalizedRootPath,
      })

      handleCreateDialogOpenChange(false)
      setIsManageDialogOpen(false)
      notify({
        description: `${createdWorkspace.name} is ready to use.`,
        title: "Workspace ready",
        tone: "success",
      })
    } catch (error) {
      setCreateNotice({
        description:
          error instanceof Error
            ? error.message
            : "The workspace could not be created.",
        title: "Could not create workspace",
        tone: "error",
      })
    }
  }

  const activeWorkspaceLabel =
    workspace.activeWorkspace?.name ??
    (workspace.status === "loading" ? "Loading workspaces" : "Select workspace")

  return (
    <>
      <DropdownMenu onOpenChange={setIsDropdownOpen} open={isDropdownOpen}>
        <DropdownMenuTrigger asChild>
          <Button
            aria-label="Select workspace"
            className="max-w-[15rem] justify-between gap-2"
            size="sm"
            variant="outline"
          >
            <span className="min-w-0 truncate">{activeWorkspaceLabel}</span>
            {workspace.status === "loading" ? (
              <LoaderCircle className="size-4 shrink-0 animate-spin" />
            ) : (
              <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[20rem]">
          <DropdownMenuLabel className="space-y-1">
            <span className="block text-xs tracking-wide uppercase">
              Workspace
            </span>
            <span className="block truncate text-sm font-medium text-foreground normal-case">
              {activeWorkspaceLabel}
            </span>
            {workspace.activeWorkspace?.root_path ? (
              <span className="block truncate font-normal normal-case">
                {workspace.activeWorkspace.root_path}
              </span>
            ) : null}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />

          {workspace.workspaces.length > 0 ? (
            <DropdownMenuRadioGroup value={workspace.activeWorkspaceId ?? ""}>
              {workspace.workspaces.map((item) => (
                <DropdownMenuRadioItem
                  className="items-start"
                  disabled={
                    item.status !== "ready" ||
                    (workspace.activatingWorkspaceId !== null &&
                      workspace.activatingWorkspaceId !== item.id)
                  }
                  key={item.id}
                  onSelect={() => {
                    void handleActivateWorkspace(item.id)
                  }}
                  value={item.id}
                >
                  <div className="min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium">{item.name}</span>
                      {item.id === workspace.activeWorkspaceId ? (
                        <Badge variant="secondary">Active</Badge>
                      ) : null}
                    </div>
                    <p className="truncate text-xs text-muted-foreground">
                      {item.root_path}
                    </p>
                  </div>
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          ) : (
            <DropdownMenuItem disabled>No workspaces yet</DropdownMenuItem>
          )}

          <DropdownMenuSeparator />
          <DropdownMenuItem
            disabled={!canBrowseDirectories || workspace.isCreatingWorkspace}
            onSelect={(event) => {
              event.preventDefault()
              setIsDropdownOpen(false)
              void beginCreateWorkspaceFlow()
            }}
          >
            <Plus className="size-4" />
            Create workspace...
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={(event) => {
              event.preventDefault()
              setIsDropdownOpen(false)
              setIsManageDialogOpen(true)
            }}
          >
            <FolderOpen className="size-4" />
            Manage workspaces...
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog onOpenChange={setIsManageDialogOpen} open={isManageDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Manage workspaces</DialogTitle>
            <DialogDescription>
              Switch between registered workspaces or create one in a new
              working directory.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {workspace.error ? (
              <InlineNotice
                description={workspace.error}
                title="Workspace registry unavailable"
                tone="error"
              />
            ) : null}

            {workspace.workspaces.length === 0 ? (
              <div className="rounded-lg border border-dashed px-4 py-8 text-center">
                <p className="text-sm font-medium text-foreground">
                  No workspaces have been registered yet.
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Choose a working directory to create or open your first
                  workspace.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {workspace.workspaces.map((item) => (
                  <div
                    className="flex flex-col gap-3 rounded-xl border bg-card px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
                    key={item.id}
                  >
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-foreground">
                          {item.name}
                        </span>
                        <Badge variant={getWorkspaceStatusVariant(item)}>
                          {getWorkspaceStatusLabel(item)}
                        </Badge>
                        {item.id === workspace.activeWorkspaceId ? (
                          <Badge variant="secondary">
                            <CheckCircle2 className="size-3.5" />
                            Active
                          </Badge>
                        ) : null}
                      </div>
                      <div className="space-y-1 text-sm text-muted-foreground">
                        <p className="break-all">{item.root_path}</p>
                        <p className="break-all">
                          Workspace data: {item.workspace_dir}
                        </p>
                      </div>
                    </div>

                    <Button
                      disabled={
                        item.status !== "ready" ||
                        item.id === workspace.activeWorkspaceId ||
                        workspace.activatingWorkspaceId !== null
                      }
                      onClick={() => {
                        void handleActivateWorkspace(item.id)
                      }}
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      {workspace.activatingWorkspaceId === item.id ? (
                        <LoaderCircle className="size-4 animate-spin" />
                      ) : null}
                      {item.id === workspace.activeWorkspaceId
                        ? "Current workspace"
                        : "Use workspace"}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              disabled={!canBrowseDirectories || workspace.isCreatingWorkspace}
              onClick={() => {
                void (async () => {
                  const didOpenCreateDialog = await beginCreateWorkspaceFlow()
                  if (didOpenCreateDialog) {
                    setIsManageDialogOpen(false)
                  }
                })()
              }}
              type="button"
              variant="outline"
            >
              <Plus className="size-4" />
              Create workspace
            </Button>
            <Button onClick={() => setIsManageDialogOpen(false)} type="button">
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        onOpenChange={handleCreateDialogOpenChange}
        open={isCreateDialogOpen}
      >
        <DialogContent
          className="max-w-lg"
          showCloseButton={!workspace.isCreatingWorkspace}
        >
          <DialogHeader>
            <DialogTitle>Create workspace</DialogTitle>
            <DialogDescription>
              Confirm the display name for the selected working directory.
              Existing `.hephaes` folders are registered instead of recreated.
            </DialogDescription>
          </DialogHeader>

          <form
            className="space-y-4"
            onSubmit={(event) => void handleCreateWorkspace(event)}
          >
            {createNotice ? (
              <InlineNotice
                description={createNotice.description}
                title={createNotice.title}
                tone={createNotice.tone}
              />
            ) : null}

            <div className="space-y-2">
              <Label
                className="text-xs tracking-wide text-muted-foreground uppercase"
                htmlFor="workspace-root-path"
              >
                Working directory
              </Label>
              <div
                className="rounded-lg border bg-muted/20 px-3 py-2 text-sm text-muted-foreground"
                id="workspace-root-path"
              >
                {createDraft.rootPath}
              </div>
            </div>

            <div className="space-y-2">
              <Label
                className="text-xs tracking-wide text-muted-foreground uppercase"
                htmlFor="workspace-name"
              >
                Workspace name
              </Label>
              <Input
                autoFocus
                disabled={workspace.isCreatingWorkspace}
                id="workspace-name"
                onChange={(event) => {
                  setCreateDraft((current) => ({
                    ...current,
                    name: event.target.value,
                  }))
                }}
                placeholder="Project workspace"
                value={createDraft.name}
              />
            </div>

            <DialogFooter>
              <Button
                disabled={workspace.isCreatingWorkspace}
                onClick={() => handleCreateDialogOpenChange(false)}
                type="button"
                variant="ghost"
              >
                Cancel
              </Button>
              <Button disabled={workspace.isCreatingWorkspace} type="submit">
                {workspace.isCreatingWorkspace ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : null}
                {workspace.isCreatingWorkspace
                  ? "Creating..."
                  : "Create workspace"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
