import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"

import { InventoryScanDialog } from "@/features/inventory/inventory-scan-dialog"
import {
  normalizeFrontendRuntime,
  setFrontendRuntime,
} from "@/lib/backend-runtime"

const { mockOpenDirectoryDialog, mockScan, mockToastError } = vi.hoisted(
  () => ({
    mockOpenDirectoryDialog: vi.fn(),
    mockScan: vi.fn(),
    mockToastError: vi.fn(),
  })
)

vi.mock("@/hooks/use-scan-directory", () => ({
  useScanDirectory: () => ({
    isScanning: false,
    scan: mockScan,
  }),
}))

vi.mock("@/lib/native-dialogs", () => ({
  openDirectoryDialog: () => mockOpenDirectoryDialog(),
}))

vi.mock("@/components/ui/sonner", () => ({
  toast: {
    error: mockToastError,
  },
}))

describe("InventoryScanDialog", () => {
  beforeAll(() => {
    vi.stubGlobal(
      "ResizeObserver",
      class ResizeObserver {
        disconnect() {}
        observe() {}
        unobserve() {}
      }
    )
  })

  beforeEach(() => {
    mockOpenDirectoryDialog.mockReset()
    mockScan.mockReset()
    mockToastError.mockReset()
  })

  afterEach(() => {
    cleanup()
    setFrontendRuntime(undefined)
  })

  afterAll(() => {
    vi.unstubAllGlobals()
  })

  it("shows a directory-picker error instead of silently ignoring native dialog failures", async () => {
    setFrontendRuntime(
      normalizeFrontendRuntime({
        baseUrl: "http://127.0.0.1:8123",
        error: null,
        mode: "desktop-sidecar",
        status: "ready",
      })
    )
    mockOpenDirectoryDialog.mockResolvedValue({
      error: "The native directory picker is unavailable.",
      status: "error",
    })

    render(
      <InventoryScanDialog
        onOpenChange={vi.fn()}
        onScanComplete={vi.fn()}
        open
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /browse/i }))

    await waitFor(() => {
      expect(
        screen.getByText("Directory picker unavailable")
      ).toBeInTheDocument()
    })
    expect(
      screen.getByText(/native directory picker is unavailable/i)
    ).toBeInTheDocument()
    expect(mockScan).not.toHaveBeenCalled()
  })
})
