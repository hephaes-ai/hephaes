"use client"

import * as React from "react"

import {
  ensureDesktopBackendRuntimeSync,
  getDesktopBackendRuntime,
  subscribeToDesktopBackendRuntime,
} from "@/lib/backend-runtime"

export function useDesktopBackendRuntime() {
  React.useEffect(() => {
    void ensureDesktopBackendRuntimeSync()
  }, [])

  return React.useSyncExternalStore(
    subscribeToDesktopBackendRuntime,
    getDesktopBackendRuntime,
    getDesktopBackendRuntime
  )
}
