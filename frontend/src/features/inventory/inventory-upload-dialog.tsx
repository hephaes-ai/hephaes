"use client"

import * as React from "react"
import { Upload } from "lucide-react"

import { Button } from "@/components/ui/button"
import { toast } from "@/components/ui/sonner"
import { useFrontendRuntime } from "@/hooks/use-desktop-backend-runtime"
import { useRegisterAssetPaths } from "@/hooks/use-register-asset-paths"
import { useUploadAssets } from "@/hooks/use-upload-assets"
import { openAssetFileDialog } from "@/lib/native-dialogs"
import type { NoticeMessage } from "@/lib/types"

export function InventoryUploadButton({
  onUploadComplete,
}: {
  onUploadComplete: (notice: NoticeMessage | null) => void
}) {
  const {
    isRegistering,
    progress: registerProgress,
    registerPaths,
  } = useRegisterAssetPaths()
  const { isUploading, progress: uploadProgress, upload } = useUploadAssets()
  const runtime = useFrontendRuntime()
  const inputRef = React.useRef<HTMLInputElement | null>(null)
  const canUseNativeDialog =
    runtime?.capabilities.nativeFileDialog &&
    runtime.capabilities.pathAssetRegistration
  const canUseBrowserUpload = runtime?.capabilities.browserUpload ?? false
  const isBusy = isRegistering || isUploading
  const progress = registerProgress ?? uploadProgress

  function handleResult(result: {
    notice: NoticeMessage | null
    toastAction: { title: string; description: string } | null
  }) {
    if (result.toastAction) {
      toast.success(result.toastAction.title, {
        description: result.toastAction.description,
      })
    }

    if (result.notice) {
      toast[result.notice.tone](result.notice.title, {
        description: result.notice.description,
      })
    }

    onUploadComplete(result.notice)
  }

  function handleDialogFailure(description: string) {
    const notice: NoticeMessage = {
      description,
      title: "File picker unavailable",
      tone: "error",
    }

    toast.error(notice.title, { description: notice.description })
    onUploadComplete(notice)
  }

  async function onOpenPicker() {
    if (isBusy) {
      return
    }

    if (canUseNativeDialog) {
      const dialogResult = await openAssetFileDialog()

      if (dialogResult.status === "error") {
        handleDialogFailure(dialogResult.error)
        return
      }

      if (dialogResult.status === "cancelled") {
        return
      }

      const result = await registerPaths(dialogResult.paths)
      handleResult(result)
      return
    }

    if (canUseBrowserUpload) {
      inputRef.current?.click()
      return
    }

    handleDialogFailure(
      "This runtime does not support registering local file paths or browser uploads from the inventory screen."
    )
  }

  async function onFilesSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ""

    if (files.length === 0) {
      return
    }

    const result = await upload(files)
    handleResult(result)
  }

  const buttonLabel =
    isBusy && progress
      ? `Adding ${progress.completed}/${progress.total}`
      : canUseBrowserUpload && !canUseNativeDialog
        ? "Upload files"
        : "Add files"

  return (
    <>
      <Button
        className="shrink-0"
        disabled={isBusy}
        onClick={() => {
          void onOpenPicker()
        }}
        size="sm"
        type="button"
        variant="outline"
      >
        <Upload className="size-4" />
        {buttonLabel}
      </Button>
      {canUseBrowserUpload ? (
        <input
          accept=".bag,.mcap"
          className="sr-only"
          multiple
          onChange={(event) => {
            void onFilesSelected(event)
          }}
          ref={inputRef}
          type="file"
        />
      ) : null}
    </>
  )
}
