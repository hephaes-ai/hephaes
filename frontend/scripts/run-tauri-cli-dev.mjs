import { spawn } from "node:child_process"

const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000"

function resolveTauriCommand() {
  return process.platform === "win32" ? "tauri.cmd" : "tauri"
}

function resolveMode(argv) {
  const explicitModeIndex = argv.indexOf("--mode")
  if (explicitModeIndex >= 0) {
    return argv[explicitModeIndex + 1] === "external" ? "external" : "sidecar"
  }

  return process.env.HEPHAES_TAURI_DEV_MODE?.trim().toLowerCase() === "sidecar"
    ? "sidecar"
    : "external"
}

const mode = resolveMode(process.argv.slice(2))
const env = { ...process.env }

if (mode === "external") {
  const configuredBaseUrl = env.VITE_BACKEND_BASE_URL?.trim()
  env.VITE_BACKEND_BASE_URL =
    configuredBaseUrl && configuredBaseUrl.length > 0
      ? configuredBaseUrl
      : DEFAULT_BACKEND_BASE_URL
  delete env.HEPHAES_TAURI_DEV_MODE
  console.log(
    `[tauri:dev] using external backend at ${env.VITE_BACKEND_BASE_URL}`,
  )
} else {
  env.HEPHAES_TAURI_DEV_MODE = "sidecar"
  delete env.VITE_BACKEND_BASE_URL
  console.log("[tauri:dev] using the packaged backend sidecar in dev")
}

const child = spawn(resolveTauriCommand(), ["dev"], {
  env,
  shell: false,
  stdio: "inherit",
})

child.on("error", (error) => {
  console.error(`[tauri:dev] ${error.message}`)
  process.exit(1)
})

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
    return
  }

  process.exit(code ?? 1)
})
