import { spawn } from "node:child_process"

const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000"

function resolveNpmCommand() {
  return process.platform === "win32" ? "npm.cmd" : "npm"
}

function runCommand(command, args, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      env,
      shell: false,
      stdio: "inherit",
    })

    child.on("error", reject)
    child.on("exit", (code, signal) => {
      if (code === 0) {
        resolve()
        return
      }

      if (signal) {
        reject(new Error(`${command} ${args.join(" ")} exited from signal ${signal}`))
        return
      }

      reject(new Error(`${command} ${args.join(" ")} exited with status ${code}`))
    })
  })
}

async function main() {
  const explicitModeIndex = process.argv.indexOf("--mode")
  const mode =
    explicitModeIndex >= 0
      ? process.argv[explicitModeIndex + 1] === "external"
        ? "external"
        : "sidecar"
      : process.env.HEPHAES_TAURI_DEV_MODE?.trim().toLowerCase() === "external"
        ? "external"
        : "sidecar"
  const env = { ...process.env }
  const npmCommand = resolveNpmCommand()

  if (mode === "external") {
    const configuredBaseUrl = env.VITE_BACKEND_BASE_URL?.trim()
    env.VITE_BACKEND_BASE_URL =
      configuredBaseUrl && configuredBaseUrl.length > 0
        ? configuredBaseUrl
        : DEFAULT_BACKEND_BASE_URL
    console.log(
      `[desktop:tauri-dev] using external backend at ${env.VITE_BACKEND_BASE_URL}`,
    )
    console.log(
      "[desktop:tauri-dev] start the backend separately before launching Tauri.",
    )
    await runCommand(npmCommand, ["run", "dev"], env)
    return
  }

  console.log("[desktop:tauri-dev] staging the packaged backend sidecar for dev")
  await runCommand(npmCommand, ["run", "tauri:prepare-backend:clean"], env)
  await runCommand(npmCommand, ["run", "dev"], env)
}

main().catch((error) => {
  console.error(`[desktop:tauri-dev] ${error.message}`)
  process.exit(1)
})
