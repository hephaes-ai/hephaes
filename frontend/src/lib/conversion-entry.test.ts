import { afterEach, describe, expect, it, vi } from "vitest"

import { resolveConversionEntry } from "@/lib/conversion-entry"

describe("resolveConversionEntry", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("routes to the saved-config flow when configs exist", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      json: async () => [
        { id: "config-a", name: "Primary config" },
        { id: "config-b", name: "Secondary config" },
      ],
      ok: true,
    })

    vi.stubGlobal("fetch", fetchMock)

    const resolution = await resolveConversionEntry(
      new URLSearchParams({
        asset_ids: "asset-1,asset-2",
        from: "/inventory",
        saved_config_id: "config-b",
        source_asset_id: "asset-1",
      })
    )

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/conversion-configs",
      { cache: "no-store" }
    )
    expect(resolution).toEqual({
      href: "/convert/use?asset_ids=asset-1%2Casset-2&saved_config_id=config-b&source_asset_id=asset-1&from=%2Finventory",
      status: "ready",
    })
  })

  it("routes to the create flow when there are no saved configs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        json: async () => [],
        ok: true,
      })
    )

    const resolution = await resolveConversionEntry(
      new URLSearchParams({
        asset_ids: "asset-1",
        from: "/inventory",
      })
    )

    expect(resolution).toEqual({
      href: "/convert/new?asset_ids=asset-1&from=%2Finventory",
      status: "ready",
    })
  })

  it("returns an error instead of silently choosing a flow when config loading fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("connection refused"))
    )

    const resolution = await resolveConversionEntry(
      new URLSearchParams({
        asset_ids: "asset-1",
      })
    )

    expect(resolution).toEqual({
      error: "connection refused",
      status: "error",
    })
  })
})
