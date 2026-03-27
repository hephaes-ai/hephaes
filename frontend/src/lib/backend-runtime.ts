export type DesktopBackendMode = "external" | "sidecar"
export type DesktopBackendStatus = "failed" | "ready" | "stopped"

export interface DesktopBackendRuntime {
  backendLogDir?: string | null
  baseUrl: string
  desktopLogDir?: string | null
  error?: string | null
  mode: DesktopBackendMode
  status: DesktopBackendStatus
}

const BACKEND_RUNTIME_EVENT = "hephaes://backend-runtime"
const BACKEND_RUNTIME_CHANGE_EVENT = "hephaes:backend-runtime-change"

declare global {
  var __HEPHAES_BACKEND_RUNTIME__: DesktopBackendRuntime | undefined
}

function normalizeBaseUrl(baseUrl: string | undefined | null) {
  return baseUrl?.trim().replace(/\/+$/, "") || ""
}

function notifyDesktopBackendRuntimeChanged() {
  if (typeof window === "undefined") {
    return
  }

  window.dispatchEvent(new Event(BACKEND_RUNTIME_CHANGE_EVENT))
}

export function setDesktopBackendRuntime(
  runtime: DesktopBackendRuntime | null | undefined
) {
  if (!runtime) {
    globalThis.__HEPHAES_BACKEND_RUNTIME__ = undefined
    globalThis.__HEPHAES_BACKEND_BASE_URL__ = undefined
    notifyDesktopBackendRuntimeChanged()
    return
  }

  const normalizedBaseUrl = normalizeBaseUrl(runtime.baseUrl)
  const nextRuntime = {
    ...runtime,
    baseUrl: normalizedBaseUrl,
  }

  globalThis.__HEPHAES_BACKEND_RUNTIME__ = nextRuntime
  globalThis.__HEPHAES_BACKEND_BASE_URL__ = normalizedBaseUrl || undefined
  notifyDesktopBackendRuntimeChanged()
}

export function getDesktopBackendRuntime() {
  if (typeof globalThis === "undefined") {
    return undefined
  }

  return globalThis.__HEPHAES_BACKEND_RUNTIME__
}

let backendRuntimeSyncPromise: Promise<void> | null = null

export function subscribeToDesktopBackendRuntime(onChange: () => void) {
  if (typeof window === "undefined") {
    return () => {}
  }

  window.addEventListener(BACKEND_RUNTIME_CHANGE_EVENT, onChange)

  return () => {
    window.removeEventListener(BACKEND_RUNTIME_CHANGE_EVENT, onChange)
  }
}

export async function ensureDesktopBackendRuntimeSync() {
  if (backendRuntimeSyncPromise) {
    return backendRuntimeSyncPromise
  }

  backendRuntimeSyncPromise = (async () => {
    try {
      const { listen } = await import("@tauri-apps/api/event")
      await listen<DesktopBackendRuntime>(BACKEND_RUNTIME_EVENT, (event) => {
        setDesktopBackendRuntime(event.payload)
      })
    } catch {
      backendRuntimeSyncPromise = null
    }
  })()

  return backendRuntimeSyncPromise
}

export async function loadDesktopBackendRuntime() {
  const configuredBaseUrl = normalizeBaseUrl(
    import.meta.env.VITE_BACKEND_BASE_URL
  )
  if (configuredBaseUrl) {
    const runtime: DesktopBackendRuntime = {
      baseUrl: configuredBaseUrl,
      error: null,
      mode: "external",
      status: "ready",
    }
    setDesktopBackendRuntime(runtime)
    return runtime
  }

  try {
    const { invoke } = await import("@tauri-apps/api/core")
    const runtime = await invoke<DesktopBackendRuntime>("get_backend_runtime")
    setDesktopBackendRuntime(runtime)
    await ensureDesktopBackendRuntimeSync()
    return runtime
  } catch {
    return undefined
  }
}
