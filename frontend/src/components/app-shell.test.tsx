import * as React from "react"
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"

import { AppShell } from "@/components/app-shell"
import { useAppRouter } from "@/lib/app-routing"

vi.mock("@/components/backend-connection-notice", () => ({
  BackendConnectionNotice: () => null,
}))

vi.mock("@/components/backend-status", () => ({
  BackendStatus: () => null,
}))

vi.mock("@/components/theme-toggle", () => ({
  ThemeToggle: () => null,
}))

function DashboardWithStaleNavigation() {
  const router = useAppRouter()

  React.useEffect(() => {
    window.setTimeout(() => {
      router.replace("/inventory", { scroll: false })
    }, 25)
  }, [router])

  return <div>Dashboard content</div>
}

describe("AppShell", () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it("navigates to another primary route with a single click", () => {
    render(
      <React.StrictMode>
        <MemoryRouter initialEntries={["/dashboard"]}>
          <AppShell>
            <Routes>
              <Route element={<div>Dashboard content</div>} path="/dashboard" />
              <Route element={<div>Inventory content</div>} path="/inventory" />
            </Routes>
          </AppShell>
        </MemoryRouter>
      </React.StrictMode>
    )

    expect(screen.getByText("Dashboard content")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("link", { name: "Inventory" }))

    expect(screen.getByText("Inventory content")).toBeInTheDocument()
    expect(
      screen.getByRole("link", { current: "page", name: "Inventory" })
    ).toBeInTheDocument()
  })

  it("does not let stale route updates override header navigation", () => {
    vi.useFakeTimers()

    render(
      <React.StrictMode>
        <MemoryRouter initialEntries={["/dashboard"]}>
          <AppShell>
            <Routes>
              <Route
                element={<DashboardWithStaleNavigation />}
                path="/dashboard"
              />
              <Route element={<div>Inventory content</div>} path="/inventory" />
              <Route element={<div>Jobs content</div>} path="/jobs" />
            </Routes>
          </AppShell>
        </MemoryRouter>
      </React.StrictMode>
    )

    fireEvent.click(screen.getByRole("link", { name: "Jobs" }))

    act(() => {
      vi.advanceTimersByTime(50)
    })

    expect(screen.getByText("Jobs content")).toBeInTheDocument()
  })
})
