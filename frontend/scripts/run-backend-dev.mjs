import { spawn } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, "..", "..")
const backendDir = path.join(repoRoot, "backend")
const backendDataDir = path.join(repoRoot, ".dev", "backend")

const command = process.platform === "win32" ? "python.exe" : "python"
const args = [
  "-m",
  "uvicorn",
  "app.main:app",
  "--reload",
  "--host",
  "127.0.0.1",
  "--port",
  "8000",
]

const env = {
  ...process.env,
  HEPHAES_BACKEND_DATA_DIR: process.env.HEPHAES_BACKEND_DATA_DIR || backendDataDir,
}

console.log(
  `[backend:dev] starting backend on http://127.0.0.1:8000 using data dir ${env.HEPHAES_BACKEND_DATA_DIR}`,
)

const child = spawn(command, args, {
  cwd: backendDir,
  env,
  shell: false,
  stdio: "inherit",
})

child.on("error", (error) => {
  console.error(`[backend:dev] ${error.message}`)
  process.exit(1)
})

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
    return
  }

  process.exit(code ?? 1)
})
