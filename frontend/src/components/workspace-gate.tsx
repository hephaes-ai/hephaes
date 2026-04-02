"use client"

import * as React from "react"
import { FolderOpen, RefreshCw, ShieldAlert } from "lucide-react"

import { InlineNotice } from "@/components/inline-notice"
import { useWorkspace } from "@/components/workspace-provider"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import {
  requestOpenCreateWorkspace,
  requestOpenManageWorkspaces,
} from "@/lib/workspace-ui-events"

function WorkspaceLoadingCard({
  description,
  title,
}: {
  description: string
  title: string
}) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <Progress />
        </CardContent>
      </Card>
    </div>
  )
}

function WorkspaceStatusChip({
  status,
}: {
  status: "invalid" | "missing" | "ready"
}) {
  if (status === "ready") {
    return <Badge variant="outline">Ready</Badge>
  }

  return (
    <Badge variant="destructive">
      {status === "missing" ? "Missing" : "Invalid"}
    </Badge>
  )
}

export function WorkspaceGate({ children }: { children: React.ReactNode }) {
  const workspace = useWorkspace()
  const readyWorkspaces = workspace.workspaces.filter(
    (item) => item.status === "ready"
  )

  if (workspace.status === "loading" && workspace.workspaces.length === 0) {
    return (
      <WorkspaceLoadingCard
        description="Checking the desktop workspace registry before opening the app."
        title="Loading workspaces"
      />
    )
  }

  if (workspace.workspaces.length === 0) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card className="w-full max-w-2xl">
          <CardHeader>
            <CardTitle>Create your first workspace</CardTitle>
            <CardDescription>
              Hephaes needs a workspace before you can browse assets, jobs, or
              outputs. Choose a working directory to create one, or open an
              existing `.hephaes` workspace.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {workspace.error ? (
              <InlineNotice
                description={workspace.error}
                title="Workspace registry unavailable"
                tone="error"
              />
            ) : null}
            <div className="rounded-xl border border-dashed bg-muted/20 px-4 py-4 text-sm text-muted-foreground">
              The workspace registry is empty, so the app is pausing here until
              you create or open one.
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-2 sm:flex-row sm:justify-end">
            <Button
              onClick={() => requestOpenCreateWorkspace("open")}
              type="button"
              variant="outline"
            >
              <FolderOpen className="size-4" />
              Open existing workspace
            </Button>
            <Button
              onClick={() => requestOpenCreateWorkspace("create")}
              type="button"
            >
              Create workspace
            </Button>
          </CardFooter>
        </Card>
      </div>
    )
  }

  if (readyWorkspaces.length === 0) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card className="w-full max-w-3xl">
          <CardHeader>
            <CardTitle>Workspace recovery needed</CardTitle>
            <CardDescription>
              Registered workspaces were found, but none of them are currently
              ready to open. Review the entries below, remove stale ones, or
              open another workspace.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {workspace.error ? (
              <InlineNotice
                description={workspace.error}
                title="Workspace registry unavailable"
                tone="error"
              />
            ) : null}

            <div className="space-y-3">
              {workspace.workspaces.map((item) => (
                <div
                  className="rounded-xl border bg-card px-4 py-4"
                  key={item.id}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-foreground">
                      {item.name}
                    </span>
                    <WorkspaceStatusChip status={item.status} />
                  </div>
                  <p className="mt-2 text-sm break-all text-muted-foreground">
                    {item.root_path}
                  </p>
                  {item.status_reason ? (
                    <p className="mt-2 text-sm text-muted-foreground">
                      {item.status_reason}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
            <Button
              onClick={() => {
                void workspace.refreshWorkspaces()
              }}
              type="button"
              variant="outline"
            >
              <RefreshCw className="size-4" />
              Refresh status
            </Button>
            <Button
              onClick={() => requestOpenManageWorkspaces()}
              type="button"
              variant="outline"
            >
              <ShieldAlert className="size-4" />
              Manage workspaces
            </Button>
            <Button
              onClick={() => requestOpenCreateWorkspace("open")}
              type="button"
              variant="outline"
            >
              <FolderOpen className="size-4" />
              Open existing workspace
            </Button>
            <Button
              onClick={() => requestOpenCreateWorkspace("create")}
              type="button"
            >
              Create workspace
            </Button>
          </CardFooter>
        </Card>
      </div>
    )
  }

  if (!workspace.activeWorkspace) {
    return (
      <WorkspaceLoadingCard
        description="Selecting the last used ready workspace before loading your data."
        title="Restoring workspace"
      />
    )
  }

  return <>{children}</>
}
