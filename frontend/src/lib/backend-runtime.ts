export type DesktopBackendMode = "external" | "sidecar"
export type DesktopBackendStatus = "failed" | "ready"

export interface DesktopBackendRuntime {
  baseUrl: string
  error?: string | null
  mode: DesktopBackendMode
  status: DesktopBackendStatus
}

declare global {
  var __HEPHAES_BACKEND_RUNTIME__: DesktopBackendRuntime | undefined
}

function normalizeBaseUrl(baseUrl: string | undefined | null) {
  return baseUrl?.trim().replace(/\/+$/, "") || ""
}

export function setDesktopBackendRuntime(
  runtime: DesktopBackendRuntime | null | undefined,
) {
  if (!runtime) {
    globalThis.__HEPHAES_BACKEND_RUNTIME__ = undefined
    return
  }

  const normalizedBaseUrl = normalizeBaseUrl(runtime.baseUrl)
  const nextRuntime = {
    ...runtime,
    baseUrl: normalizedBaseUrl,
  }

  globalThis.__HEPHAES_BACKEND_RUNTIME__ = nextRuntime
  globalThis.__HEPHAES_BACKEND_BASE_URL__ = normalizedBaseUrl || undefined
}

export function getDesktopBackendRuntime() {
  if (typeof globalThis === "undefined") {
    return undefined
  }

  return globalThis.__HEPHAES_BACKEND_RUNTIME__
}

export async function loadDesktopBackendRuntime() {
  const configuredBaseUrl = normalizeBaseUrl(import.meta.env.VITE_BACKEND_BASE_URL)
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
    return runtime
  } catch {
    return undefined
  }
}
