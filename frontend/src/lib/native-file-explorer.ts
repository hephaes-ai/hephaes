"use client"

export interface NativeFileExplorerFailure {
  error: string
  status: "error"
}

export interface NativeFileExplorerSuccess {
  status: "opened"
}

export type NativeFileExplorerResult =
  | NativeFileExplorerFailure
  | NativeFileExplorerSuccess

function buildFileExplorerFailure(error: unknown): NativeFileExplorerFailure {
  const detail =
    error instanceof Error && error.message.trim()
      ? ` ${error.message.trim()}`
      : ""

  return {
    error:
      `The desktop app could not open the local path in Finder or File Explorer.${detail}`.trim(),
    status: "error",
  }
}

export async function revealPathInFileExplorer(
  path: string
): Promise<NativeFileExplorerResult> {
  const trimmedPath = path.trim()
  if (!trimmedPath) {
    return {
      error: "The output does not expose a local file path yet.",
      status: "error",
    }
  }

  try {
    const { invoke, isTauri } = await import("@tauri-apps/api/core")

    if (!isTauri()) {
      return {
        error: "Revealing local paths is only available in the desktop app.",
        status: "error",
      }
    }

    await invoke("reveal_in_file_explorer", {
      path: trimmedPath,
    })

    return { status: "opened" }
  } catch (error) {
    return buildFileExplorerFailure(error)
  }
}
