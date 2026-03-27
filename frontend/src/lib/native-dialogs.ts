"use client"

function normalizeSelection(
  selection: string | string[] | null,
): string[] {
  if (!selection) {
    return []
  }

  const values = Array.isArray(selection) ? selection : [selection]

  return values
    .map((value) => value.trim())
    .filter(Boolean)
}

export async function openAssetFileDialog() {
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
    return normalizeSelection(selection)
  } catch {
    return null
  }
}

export async function openDirectoryDialog() {
  try {
    const { open } = await import("@tauri-apps/plugin-dialog")
    const selection = await open({
      directory: true,
      multiple: false,
      title: "Select directory to scan",
    })
    const [directoryPath] = normalizeSelection(selection)
    return directoryPath ?? null
  } catch {
    return null
  }
}
