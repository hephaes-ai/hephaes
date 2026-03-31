import * as React from "react"

import App from "@/App"
import { AppProviders } from "@/components/app-providers"
import { Progress } from "@/components/ui/progress"
import { useFrontendRuntime } from "@/hooks/use-desktop-backend-runtime"
import {
  loadFrontendRuntime,
  setFrontendRuntime,
  type FrontendRuntimeSnapshot,
} from "@/lib/backend-runtime"

type BootstrapState =
  | { status: "loading" }
  | { runtime: FrontendRuntimeSnapshot; status: "failed" }
  | { status: "ready" }

export function StartupScreen() {
  return (
    <AppProviders>
      <div className="flex min-h-svh items-center justify-center bg-background">
        <Progress className="w-56" />
      </div>
    </AppProviders>
  )
}

export function BootstrapApp({
  loadRuntime = loadFrontendRuntime,
  readyFallback = <App />,
}: {
  loadRuntime?: () => Promise<FrontendRuntimeSnapshot | undefined>
  readyFallback?: React.ReactNode
}) {
  const [state, setState] = React.useState<BootstrapState>({
    status: "loading",
  })
  const [hasLoadedRuntime, setHasLoadedRuntime] = React.useState(false)
  const [startupComplete, setStartupComplete] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      const runtime = await loadRuntime()

      if (cancelled) {
        return
      }

      if (runtime) {
        setFrontendRuntime(runtime)
      }

      setHasLoadedRuntime(true)
    }

    void bootstrap()

    return () => {
      cancelled = true
    }
  }, [loadRuntime])

  const runtime = useFrontendRuntime()

  React.useEffect(() => {
    if (!hasLoadedRuntime || !runtime) {
      return
    }

    if (runtime.status === "ready") {
      setStartupComplete(true)
      setState({ status: "ready" })
      return
    }

    if (!startupComplete && runtime.status === "loading") {
      setState({ status: "loading" })
      return
    }

    if (!startupComplete) {
      setState({
        runtime,
        status: "failed",
      })
    }
  }, [hasLoadedRuntime, runtime, startupComplete])

  if (
    !hasLoadedRuntime ||
    state.status === "loading" ||
    (!startupComplete && runtime?.status === "loading")
  ) {
    return (
      <StartupScreen />
    )
  }

  if (state.status === "failed") {
    const runtimeLabel =
      state.runtime.mode === "desktop-sidecar"
        ? "the bundled backend"
        : state.runtime.mode === "desktop-external"
          ? "the configured external backend"
          : "the configured backend"
    const baseUrl = state.runtime.baseUrl?.trim()
    const errorText = state.runtime.error?.trim()
    const details = [
      `The desktop app could not finish starting ${runtimeLabel}.`,
      baseUrl ? `Target URL: ${baseUrl}.` : null,
      errorText ? `Error: ${errorText}` : null,
      state.runtime.backendLogDir
        ? `Backend logs: ${state.runtime.backendLogDir}.`
        : null,
      state.runtime.desktopLogDir
        ? `Desktop logs: ${state.runtime.desktopLogDir}.`
        : null,
    ]
      .filter(Boolean)
      .join(" ")

    return (
      <StartupScreen />
    )
  }

  return readyFallback
}
