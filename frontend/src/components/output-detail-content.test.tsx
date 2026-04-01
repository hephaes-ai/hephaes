import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import {
  OutputDetailContent,
  buildOutputPreview,
} from "@/components/output-detail-content"
import type { AssetSummary, OutputDetail } from "@/lib/api"

afterEach(() => {
  cleanup()
})

function buildBaseOutput(): OutputDetail {
  return {
    asset_ids: ["asset-1"],
    availability_status: "ready",
    content_url: "/outputs/output-1/content",
    conversion_id: "conv-1",
    created_at: "2026-03-22T00:00:00Z",
    file_name: "dataset.tfrecord",
    format: "tfrecord",
    id: "output-1",
    job_id: "job-1",
    media_type: "application/octet-stream",
    metadata: {
      manifest: {
        dataset: {
          rows_written: 120,
        },
        payload_representation: {
          image_payload_contract: "bytes_v2",
          null_encoding: "presence_flag",
          payload_encoding: "typed_features",
        },
        temporal: {
          message_count: 120,
        },
      },
    },
    relative_path: "runs/conv-1/dataset.tfrecord",
    role: "dataset",
    size_bytes: 1024,
    updated_at: "2026-03-22T00:01:00Z",
  }
}

describe("buildOutputPreview", () => {
  it("includes payload representation details for tfrecord outputs", () => {
    const preview = buildOutputPreview(buildBaseOutput())
    const imagePayloadFact = preview.facts.find(
      (fact) => fact.label === "Image payload"
    )

    expect(imagePayloadFact?.value).toBe("bytes_v2")
    expect(preview.notes.join(" ")).toContain(
      "training-ready bytes image payload"
    )
  })
})

describe("OutputDetailContent", () => {
  it("lets users reveal the local output path from the details card", () => {
    const onCopyFilePath = vi.fn().mockResolvedValue(undefined)
    const onCopyReference = vi.fn().mockResolvedValue(undefined)
    const onRevealFilePath = vi.fn().mockResolvedValue(undefined)
    const output = {
      ...buildBaseOutput(),
      file_path: "/tmp/hephaes/outputs/dataset.tfrecord",
    }
    const sourceAsset: AssetSummary = {
      file_name: "robot-run.mcap",
      file_path: "/tmp/hephaes/assets/robot-run.mcap",
      file_size: 2048,
      file_type: "mcap",
      id: "asset-1",
      indexing_status: "indexed",
      last_indexed_time: "2026-03-22T00:02:00Z",
      registered_time: "2026-03-22T00:00:00Z",
    }

    render(
      <MemoryRouter>
        <OutputDetailContent
          assetsById={new Map([[sourceAsset.id, sourceAsset]])}
          currentHref="/outputs/output-1"
          onCopyFilePath={onCopyFilePath}
          onCopyReference={onCopyReference}
          onRevealFilePath={onRevealFilePath}
          output={output}
        />
      </MemoryRouter>
    )

    fireEvent.click(
      screen.getByRole("button", {
        name: /reveal local file path in finder or file explorer/i,
      })
    )

    expect(onRevealFilePath).toHaveBeenCalledWith(output)
  })

  it("lets users copy the raw local output path", () => {
    const onCopyFilePath = vi.fn().mockResolvedValue(undefined)
    const onCopyReference = vi.fn().mockResolvedValue(undefined)
    const onRevealFilePath = vi.fn().mockResolvedValue(undefined)
    const output = {
      ...buildBaseOutput(),
      file_path: "/tmp/hephaes/outputs/very/long/path/dataset.tfrecord",
    }

    render(
      <MemoryRouter>
        <OutputDetailContent
          assetsById={new Map()}
          currentHref="/outputs/output-1"
          onCopyFilePath={onCopyFilePath}
          onCopyReference={onCopyReference}
          onRevealFilePath={onRevealFilePath}
          output={output}
        />
      </MemoryRouter>
    )

    fireEvent.click(
      screen.getByRole("button", {
        name: /copy local file path/i,
      })
    )

    expect(onCopyFilePath).toHaveBeenCalledWith(output.file_path)
  })
})
