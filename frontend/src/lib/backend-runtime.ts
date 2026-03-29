export type FrontendMode = "desktop-external" | "desktop-sidecar" | "web"
export type FrontendRuntimeStatus = "failed" | "loading" | "ready" | "stopped"

export interface FrontendCapabilities {
  browserUpload: boolean
  nativeDirectoryDialog: boolean
  nativeFileDialog: boolean
  pathAssetRegistration: boolean
}

export interface FrontendRuntimeSnapshot {
  backendLogDir?: string | null
  baseUrl: string
  capabilities: FrontendCapabilities
  desktopLogDir?: string | null
  error?: string | null
  mode: FrontendMode
  status: FrontendRuntimeStatus
}

export type DesktopBackendMode = Exclude<FrontendMode, "web">
export type DesktopBackendStatus = FrontendRuntimeStatus
export type DesktopBackendRuntime = FrontendRuntimeSnapshot

type RuntimeInputMode = FrontendMode | "external" | "sidecar"

interface FrontendRuntimeInput extends Omit<
  FrontendRuntimeSnapshot,
  "capabilities" | "mode"
> {
  capabilities?: Partial<FrontendCapabilities> | null
  mode: RuntimeInputMode
}

const BACKEND_RUNTIME_EVENT = "hephaes://backend-runtime"
const BACKEND_RUNTIME_CHANGE_EVENT = "hephaes:backend-runtime-change"

declare global {
  var __HEPHAES_BACKEND_RUNTIME__: FrontendRuntimeSnapshot | undefined
}

const DESKTOP_CAPABILITIES: FrontendCapabilities = {
  browserUpload: false,
  nativeDirectoryDialog: true,
  nativeFileDialog: true,
  pathAssetRegistration: true,
}

const WEB_CAPABILITIES: FrontendCapabilities = {
  browserUpload: true,
  nativeDirectoryDialog: false,
  nativeFileDialog: false,
  pathAssetRegistration: false,
}

function normalizeBaseUrl(baseUrl: string | undefined | null) {
  return baseUrl?.trim().replace(/\/+$/, "") || ""
}

async function isTauriDesktopRuntimeAvailable() {
  try {
    const { isTauri } = await import("@tauri-apps/api/core")
    return isTauri()
  } catch {
    return false
  }
}

function buildDesktopRuntimeLoadError() {
  return "The desktop frontend could not communicate with the Tauri host runtime."
}

function normalizeMode(mode: RuntimeInputMode): FrontendMode {
  switch (mode) {
    case "external":
      return "desktop-external"
    case "sidecar":
      return "desktop-sidecar"
    default:
      return mode
  }
}

function resolveWindowBaseUrl() {
  if (typeof window === "undefined") {
    return ""
  }

  return normalizeBaseUrl(window.location.origin)
}

export function getFrontendRuntimeCapabilities(
  mode: FrontendMode
): FrontendCapabilities {
  return mode === "web" ? { ...WEB_CAPABILITIES } : { ...DESKTOP_CAPABILITIES }
}

export function normalizeFrontendRuntime(
  runtime: FrontendRuntimeInput
): FrontendRuntimeSnapshot {
  const mode = normalizeMode(runtime.mode)

  return {
    ...runtime,
    baseUrl: normalizeBaseUrl(runtime.baseUrl),
    capabilities: {
      ...getFrontendRuntimeCapabilities(mode),
      ...(runtime.capabilities ?? {}),
    },
    mode,
  }
}

export function createWebFrontendRuntime(
  baseUrl = resolveWindowBaseUrl()
): FrontendRuntimeSnapshot {
  return normalizeFrontendRuntime({
    baseUrl,
    error: null,
    mode: "web",
    status: "ready",
  })
}

function notifyDesktopBackendRuntimeChanged() {
  if (typeof window === "undefined") {
    return
  }

  window.dispatchEvent(new Event(BACKEND_RUNTIME_CHANGE_EVENT))
}

export function setFrontendRuntime(
  runtime: FrontendRuntimeInput | null | undefined
) {
  if (!runtime) {
    globalThis.__HEPHAES_BACKEND_RUNTIME__ = undefined
    globalThis.__HEPHAES_BACKEND_BASE_URL__ = undefined
    notifyDesktopBackendRuntimeChanged()
    return
  }

  const nextRuntime = normalizeFrontendRuntime(runtime)

  globalThis.__HEPHAES_BACKEND_RUNTIME__ = nextRuntime
  globalThis.__HEPHAES_BACKEND_BASE_URL__ = nextRuntime.baseUrl || undefined
  notifyDesktopBackendRuntimeChanged()
}

export function getFrontendRuntime() {
  if (typeof globalThis === "undefined") {
    return undefined
  }

  return globalThis.__HEPHAES_BACKEND_RUNTIME__
}

let backendRuntimeSyncPromise: Promise<void> | null = null

export function subscribeToFrontendRuntime(onChange: () => void) {
  if (typeof window === "undefined") {
    return () => {}
  }

  window.addEventListener(BACKEND_RUNTIME_CHANGE_EVENT, onChange)

  return () => {
    window.removeEventListener(BACKEND_RUNTIME_CHANGE_EVENT, onChange)
  }
}

export async function ensureFrontendRuntimeSync() {
  if (backendRuntimeSyncPromise) {
    return backendRuntimeSyncPromise
  }

  backendRuntimeSyncPromise = (async () => {
    try {
      const { listen } = await import("@tauri-apps/api/event")
      await listen<FrontendRuntimeSnapshot>(BACKEND_RUNTIME_EVENT, (event) => {
        setFrontendRuntime(event.payload)
      })
    } catch {
      backendRuntimeSyncPromise = null
    }
  })()

  return backendRuntimeSyncPromise
}

export async function loadFrontendRuntime() {
  const configuredBaseUrl = normalizeBaseUrl(
    import.meta.env.VITE_BACKEND_BASE_URL
  )
  const isTauriDesktop = await isTauriDesktopRuntimeAvailable()

  if (configuredBaseUrl) {
    const runtime = normalizeFrontendRuntime({
      baseUrl: configuredBaseUrl,
      error: null,
      mode: isTauriDesktop ? "desktop-external" : "web",
      status: "ready",
    })
    setFrontendRuntime(runtime)
    return runtime
  }

  if (!isTauriDesktop) {
    const runtime = createWebFrontendRuntime()
    setFrontendRuntime(runtime)
    return runtime
  }

  try {
    const { invoke } = await import("@tauri-apps/api/core")
    const runtime = normalizeFrontendRuntime(
      await invoke<FrontendRuntimeSnapshot>("get_backend_runtime")
    )
    setFrontendRuntime(runtime)

    try {
      await ensureFrontendRuntimeSync()
    } catch {
      // Keep the initial runtime snapshot even if live updates are unavailable.
    }

    return runtime
  } catch {
    const runtime = normalizeFrontendRuntime({
      baseUrl: "",
      error: buildDesktopRuntimeLoadError(),
      mode: "desktop-sidecar",
      status: "failed",
    })
    setFrontendRuntime(runtime)
    return runtime
  }
}

export const setDesktopBackendRuntime = setFrontendRuntime
export const getDesktopBackendRuntime = getFrontendRuntime
export const subscribeToDesktopBackendRuntime = subscribeToFrontendRuntime
export const ensureDesktopBackendRuntimeSync = ensureFrontendRuntimeSync
export const loadDesktopBackendRuntime = loadFrontendRuntime
