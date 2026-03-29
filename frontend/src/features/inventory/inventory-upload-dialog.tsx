"use client";

import * as React from "react";
import { Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { useRegisterAssetPaths } from "@/hooks/use-register-asset-paths";
import { useUploadAssets } from "@/hooks/use-upload-assets";
import { openAssetFileDialog } from "@/lib/native-dialogs";
import type { NoticeMessage } from "@/lib/types";

export function InventoryUploadButton({
  onUploadComplete,
}: {
  onUploadComplete: (notice: NoticeMessage | null) => void;
}) {
  const {
    isRegistering,
    progress: registerProgress,
    registerPaths,
  } = useRegisterAssetPaths();
  const { isUploading, progress: uploadProgress, upload } = useUploadAssets();
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const isBusy = isRegistering || isUploading;
  const progress = registerProgress ?? uploadProgress;

  function handleResult(result: {
    notice: NoticeMessage | null;
    toastAction: { title: string; description: string } | null;
  }) {
    if (result.toastAction) {
      toast.success(result.toastAction.title, { description: result.toastAction.description });
    }

    if (result.notice) {
      toast[result.notice.tone](result.notice.title, { description: result.notice.description });
    }

    onUploadComplete(result.notice);
  }

  async function onOpenPicker() {
    if (isBusy) {
      return;
    }

    const selectedPaths = await openAssetFileDialog();
    if (selectedPaths === null) {
      inputRef.current?.click();
      return;
    }

    if (selectedPaths.length === 0) {
      return;
    }

    const result = await registerPaths(selectedPaths);
    handleResult(result);
  }

  async function onFilesSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";

    if (files.length === 0) {
      return;
    }

    const result = await upload(files);
    handleResult(result);
  }

  const buttonLabel =
    isBusy && progress
      ? `Adding ${progress.completed}/${progress.total}`
      : "Add files";

  return (
    <>
      <Button
        className="shrink-0"
        disabled={isBusy}
        onClick={() => {
          void onOpenPicker();
        }}
        size="sm"
        type="button"
        variant="outline"
      >
        <Upload className="size-4" />
        {buttonLabel}
      </Button>
      <input
        accept=".bag,.mcap"
        className="sr-only"
        multiple
        onChange={(event) => {
          void onFilesSelected(event);
        }}
        ref={inputRef}
        type="file"
      />
    </>
  );
}
