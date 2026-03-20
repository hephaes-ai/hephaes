"use client";

import * as React from "react";
import { Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { useUploadAssets } from "@/hooks/use-upload-assets";
import type { NoticeMessage } from "@/lib/types";

export function InventoryUploadButton({
  onUploadComplete,
}: {
  onUploadComplete: (notice: NoticeMessage | null) => void;
}) {
  const { isUploading, progress, upload } = useUploadAssets();
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  function onOpenPicker() {
    if (isUploading) {
      return;
    }

    inputRef.current?.click();
  }

  async function onFilesSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";

    if (files.length === 0) {
      return;
    }

    const result = await upload(files);

    if (result.toastAction) {
      toast.success(result.toastAction.title, { description: result.toastAction.description });
    }

    if (result.notice) {
      toast[result.notice.tone](result.notice.title, { description: result.notice.description });
    }

    onUploadComplete(result.notice);
  }

  const buttonLabel =
    isUploading && progress
      ? `Uploading ${progress.completed}/${progress.total}`
      : "Upload files";

  return (
    <>
      <Button
        className="shrink-0"
        disabled={isUploading}
        onClick={onOpenPicker}
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
        onChange={onFilesSelected}
        ref={inputRef}
        type="file"
      />
    </>
  );
}
