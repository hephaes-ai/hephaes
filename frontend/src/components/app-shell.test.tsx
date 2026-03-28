import { fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { AppShell } from "@/components/app-shell"

vi.mock("@/components/backend-connection-notice", () => ({
  BackendConnectionNotice: () => null,
}))

vi.mock("@/components/backend-status", () => ({
  BackendStatus: () => null,
}))

vi.mock("@/components/theme-toggle", () => ({
  ThemeToggle: () => null,
}))

describe("AppShell", () => {
  it("navigates to another primary route with a single click", () => {
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AppShell>
          <Routes>
            <Route element={<div>Dashboard content</div>} path="/dashboard" />
            <Route element={<div>Inventory content</div>} path="/inventory" />
          </Routes>
        </AppShell>
      </MemoryRouter>
    )

    expect(screen.getByText("Dashboard content")).toBeInTheDocument()

    fireEvent.click(screen.getByRole("link", { name: "Inventory" }))

    expect(screen.getByText("Inventory content")).toBeInTheDocument()
    expect(
      screen.getByRole("link", { current: "page", name: "Inventory" })
    ).toBeInTheDocument()
  })
})
