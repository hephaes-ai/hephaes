import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"

import { InventoryUploadButton } from "@/features/inventory/inventory-upload-dialog"
import {
  createWebFrontendRuntime,
  normalizeFrontendRuntime,
  setFrontendRuntime,
} from "@/lib/backend-runtime"

const {
  mockOpenAssetFileDialog,
  mockRegisterPaths,
  mockToastError,
  mockToastInfo,
  mockToastSuccess,
  mockUpload,
} = vi.hoisted(() => ({
  mockOpenAssetFileDialog: vi.fn(),
  mockRegisterPaths: vi.fn(),
  mockToastError: vi.fn(),
  mockToastInfo: vi.fn(),
  mockToastSuccess: vi.fn(),
  mockUpload: vi.fn(),
}))

vi.mock("@/hooks/use-register-asset-paths", () => ({
  useRegisterAssetPaths: () => ({
    isRegistering: false,
    progress: null,
    registerPaths: mockRegisterPaths,
  }),
}))

vi.mock("@/hooks/use-upload-assets", () => ({
  useUploadAssets: () => ({
    isUploading: false,
    progress: null,
    upload: mockUpload,
  }),
}))

vi.mock("@/lib/native-dialogs", () => ({
  openAssetFileDialog: () => mockOpenAssetFileDialog(),
}))

vi.mock("@/components/ui/sonner", () => ({
  toast: {
    error: mockToastError,
    info: mockToastInfo,
    success: mockToastSuccess,
  },
}))

describe("InventoryUploadButton", () => {
  beforeEach(() => {
    mockRegisterPaths.mockReset()
    mockUpload.mockReset()
    mockOpenAssetFileDialog.mockReset()
    mockToastError.mockReset()
    mockToastInfo.mockReset()
    mockToastSuccess.mockReset()
  })

  afterEach(() => {
    cleanup()
    setFrontendRuntime(undefined)
    vi.restoreAllMocks()
  })

  it("registers selected desktop file paths instead of uploading file bytes", async () => {
    setFrontendRuntime(
      normalizeFrontendRuntime({
        baseUrl: "http://127.0.0.1:8123",
        error: null,
        mode: "desktop-sidecar",
        status: "ready",
      })
    )
    mockOpenAssetFileDialog.mockResolvedValue({
      paths: ["/tmp/demo.mcap"],
      status: "selected",
    })
    mockRegisterPaths.mockResolvedValue({
      notice: null,
      registeredCount: 1,
      toastAction: null,
    })

    render(<InventoryUploadButton onUploadComplete={vi.fn()} />)

    fireEvent.click(screen.getByRole("button", { name: /add files/i }))

    await waitFor(() => {
      expect(mockOpenAssetFileDialog).toHaveBeenCalledTimes(1)
    })
    expect(mockRegisterPaths).toHaveBeenCalledWith(["/tmp/demo.mcap"])
    expect(mockUpload).not.toHaveBeenCalled()
  })

  it("uses browser upload only when the runtime exposes browser upload capability", async () => {
    setFrontendRuntime(createWebFrontendRuntime("http://localhost:3000"))
    const clickSpy = vi
      .spyOn(HTMLInputElement.prototype, "click")
      .mockImplementation(() => {})

    render(<InventoryUploadButton onUploadComplete={vi.fn()} />)

    fireEvent.click(screen.getByRole("button", { name: /upload files/i }))

    expect(clickSpy).toHaveBeenCalledTimes(1)
    expect(mockOpenAssetFileDialog).not.toHaveBeenCalled()
  })

  it("surfaces native dialog failures instead of silently falling back to upload", async () => {
    const onUploadComplete = vi.fn()

    setFrontendRuntime(
      normalizeFrontendRuntime({
        baseUrl: "http://127.0.0.1:8123",
        error: null,
        mode: "desktop-sidecar",
        status: "ready",
      })
    )
    mockOpenAssetFileDialog.mockResolvedValue({
      error: "The native file picker is unavailable.",
      status: "error",
    })

    render(<InventoryUploadButton onUploadComplete={onUploadComplete} />)

    fireEvent.click(screen.getByRole("button", { name: /add files/i }))

    await waitFor(() => {
      expect(onUploadComplete).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "File picker unavailable",
          tone: "error",
        })
      )
    })
    expect(mockRegisterPaths).not.toHaveBeenCalled()
    expect(mockUpload).not.toHaveBeenCalled()
  })
})
