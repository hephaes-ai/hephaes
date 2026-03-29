"use client"

export interface NativeDialogFailure {
  error: string
  status: "error"
}

export interface NativeAssetFileDialogSelection {
  paths: string[]
  status: "selected"
}

export interface NativeDirectoryDialogSelection {
  directoryPath: string
  status: "selected"
}

export type NativeAssetFileDialogResult =
  | NativeAssetFileDialogSelection
  | NativeDialogFailure
  | { status: "cancelled" }

export type NativeDirectoryDialogResult =
  | NativeDirectoryDialogSelection
  | NativeDialogFailure
  | { status: "cancelled" }

function normalizeSelection(selection: string | string[] | null): string[] {
  if (!selection) {
    return []
  }

  const values = Array.isArray(selection) ? selection : [selection]

  return values.map((value) => value.trim()).filter(Boolean)
}

function buildDialogFailure(
  action: "directory picker" | "file picker",
  error: unknown
): NativeDialogFailure {
  const detail =
    error instanceof Error && error.message.trim()
      ? ` ${error.message.trim()}`
      : ""

  return {
    error: `The native ${action} is unavailable.${detail}`.trim(),
    status: "error",
  }
}

export async function openAssetFileDialog(): Promise<NativeAssetFileDialogResult> {
  try {
    const { open } = await import("@tauri-apps/plugin-dialog")
    const selection = await open({
      directory: false,
      filters: [
        {
          extensions: ["bag", "mcap"],
          name: "Supported assets",
        },
      ],
      multiple: true,
      title: "Select asset files",
    })
    const selectedPaths = normalizeSelection(selection)

    if (selectedPaths.length === 0) {
      return { status: "cancelled" }
    }

    return {
      paths: selectedPaths,
      status: "selected",
    }
  } catch (error) {
    return buildDialogFailure("file picker", error)
  }
}

export async function openDirectoryDialog(): Promise<NativeDirectoryDialogResult> {
  try {
    const { open } = await import("@tauri-apps/plugin-dialog")
    const selection = await open({
      directory: true,
      multiple: false,
      title: "Select directory to scan",
    })
    const [directoryPath] = normalizeSelection(selection)

    if (!directoryPath) {
      return { status: "cancelled" }
    }

    return {
      directoryPath,
      status: "selected",
    }
  } catch (error) {
    return buildDialogFailure("directory picker", error)
  }
}
