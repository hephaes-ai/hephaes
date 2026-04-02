import { afterEach, describe, expect, it, vi } from "vitest"

import {
  getHealth,
  listJobs,
  listWorkspaces,
  setActiveWorkspaceRequestId,
} from "@/lib/api"

describe("backend api workspace scoping", () => {
  afterEach(() => {
    setActiveWorkspaceRequestId(undefined)
    vi.unstubAllGlobals()
  })

  it("includes the active workspace header for workspace-backed requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        headers: {
          "Content-Type": "application/json",
        },
        status: 200,
      })
    )

    vi.stubGlobal("fetch", fetchMock)
    setActiveWorkspaceRequestId("ws_123")

    await listJobs()

    const requestHeaders = fetchMock.mock.calls[0]?.[1]?.headers

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/jobs",
      expect.objectContaining({
        headers: expect.any(Headers),
      })
    )
    expect(requestHeaders).toBeInstanceOf(Headers)
    expect((requestHeaders as Headers).get("X-Hephaes-Workspace-Id")).toBe(
      "ws_123"
    )
  })

  it("does not include the active workspace header for non-workspace requests", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            active_workspace_id: null,
            workspaces: [],
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
            status: 200,
          }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            app_name: "hephaes",
            status: "ok",
          }),
          {
            headers: {
              "Content-Type": "application/json",
            },
            status: 200,
          }
        )
      )

    vi.stubGlobal("fetch", fetchMock)
    setActiveWorkspaceRequestId("ws_123")

    await listWorkspaces()
    await getHealth()

    const workspaceRequestHeaders = fetchMock.mock.calls[0]?.[1]?.headers
    const healthRequestHeaders = fetchMock.mock.calls[1]?.[1]?.headers

    expect((workspaceRequestHeaders as Headers).has("X-Hephaes-Workspace-Id")).toBe(
      false
    )
    expect((healthRequestHeaders as Headers).has("X-Hephaes-Workspace-Id")).toBe(
      false
    )
  })
})
