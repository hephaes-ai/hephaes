"use client"

import * as React from "react"

import {
  ensureFrontendRuntimeSync,
  getFrontendRuntime,
  subscribeToFrontendRuntime,
} from "@/lib/backend-runtime"

export function useFrontendRuntime() {
  React.useEffect(() => {
    void ensureFrontendRuntimeSync()
  }, [])

  return React.useSyncExternalStore(
    subscribeToFrontendRuntime,
    getFrontendRuntime,
    getFrontendRuntime
  )
}

export const useDesktopBackendRuntime = useFrontendRuntime
