"use client"

import * as React from "react"
import { FolderOpen, RefreshCw } from "lucide-react"

import { InlineNotice } from "@/components/inline-notice"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "@/components/ui/sonner"
import { useScanDirectory } from "@/hooks/use-scan-directory"
import { useFrontendRuntime } from "@/hooks/use-desktop-backend-runtime"
import { openDirectoryDialog } from "@/lib/native-dialogs"
import type { NoticeMessage } from "@/lib/types"

interface DirectoryScanFormState {
  directoryPath: string
  recursive: boolean
}

const DEFAULT_FORM: DirectoryScanFormState = {
  directoryPath: "",
  recursive: true,
}

export function InventoryScanDialog({
  onScanComplete,
  onOpenChange,
  open,
}: {
  onScanComplete: (notice: NoticeMessage) => void
  onOpenChange: (open: boolean) => void
  open: boolean
}) {
  const { isScanning, scan } = useScanDirectory()
  const runtime = useFrontendRuntime()
  const [form, setForm] = React.useState<DirectoryScanFormState>(DEFAULT_FORM)
  const [dialogMessage, setDialogMessage] =
    React.useState<NoticeMessage | null>(null)
  const canBrowseDirectories =
    runtime?.capabilities.nativeDirectoryDialog ?? false

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen && isScanning) {
      return
    }

    onOpenChange(nextOpen)

    if (!nextOpen) {
      setForm(DEFAULT_FORM)
      setDialogMessage(null)
    }
  }

  async function handleBrowseForDirectory() {
    if (isScanning) {
      return
    }

    const selectedDirectory = await openDirectoryDialog()
    if (selectedDirectory.status === "error") {
      setDialogMessage({
        description: selectedDirectory.error,
        title: "Directory picker unavailable",
        tone: "error",
      })
      return
    }

    if (selectedDirectory.status === "cancelled") {
      return
    }

    setDialogMessage(null)
    setForm((current) => ({
      ...current,
      directoryPath: selectedDirectory.directoryPath,
    }))
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const normalizedPath = form.directoryPath.trim()
    if (!normalizedPath) {
      setDialogMessage({
        description: "Enter a local directory path before scanning.",
        title: "Directory required",
        tone: "error",
      })
      return
    }

    setDialogMessage(null)

    const result = await scan(normalizedPath, form.recursive)

    if (result.dialogNotice) {
      setDialogMessage(result.dialogNotice)
      toast.error("Directory scan failed", {
        description: result.dialogNotice.description,
      })
      return
    }

    handleOpenChange(false)
    onScanComplete(result.notice)
    toast[result.notice.tone](result.notice.title, {
      description: result.notice.description,
    })
  }

  return (
    <Dialog onOpenChange={handleOpenChange} open={open}>
      <DialogContent className="max-w-lg" showCloseButton={!isScanning}>
        <DialogHeader>
          <DialogTitle>Scan directory</DialogTitle>
          <DialogDescription>
            Register every supported `.bag` or `.mcap` file in a local directory
            without selecting them one by one.
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={handleSubmit}>
          {dialogMessage ? (
            <InlineNotice
              description={dialogMessage.description}
              title={dialogMessage.title}
              tone={dialogMessage.tone}
            />
          ) : null}

          <div className="space-y-2">
            <Label
              className="text-xs tracking-wide text-muted-foreground uppercase"
              htmlFor="directory-scan-path"
            >
              Directory path
            </Label>
            <div className="flex gap-2">
              <Input
                disabled={isScanning}
                id="directory-scan-path"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    directoryPath: event.target.value,
                  }))
                }
                placeholder="/path/to/recordings"
                value={form.directoryPath}
              />
              <Button
                disabled={isScanning || !canBrowseDirectories}
                onClick={() => {
                  void handleBrowseForDirectory()
                }}
                type="button"
                variant="outline"
              >
                <FolderOpen className="size-4" />
                Browse
              </Button>
            </div>
            {!canBrowseDirectories ? (
              <p className="text-xs text-muted-foreground">
                Native directory picking is unavailable in this runtime. Enter a
                directory path manually to scan it.
              </p>
            ) : null}
          </div>

          <label className="flex items-start gap-3 rounded-lg border bg-muted/20 px-3 py-3">
            <Checkbox
              checked={form.recursive}
              disabled={isScanning}
              onCheckedChange={(checked) =>
                setForm((current) => ({
                  ...current,
                  recursive: checked === true,
                }))
              }
            />
            <span className="space-y-1">
              <span className="block text-sm font-medium text-foreground">
                Scan recursively
              </span>
              <span className="block text-sm text-muted-foreground">
                Include supported files from nested directories instead of only
                the top-level folder.
              </span>
            </span>
          </label>

          <DialogFooter>
            <Button
              disabled={isScanning}
              onClick={() => handleOpenChange(false)}
              type="button"
              variant="ghost"
            >
              Cancel
            </Button>
            <Button disabled={isScanning} type="submit">
              {isScanning ? (
                <RefreshCw className="size-3.5 animate-spin" />
              ) : null}
              {isScanning ? "Scanning..." : "Scan directory"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
