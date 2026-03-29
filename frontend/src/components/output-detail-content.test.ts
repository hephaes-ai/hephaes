import { describe, expect, it } from "vitest"

import { buildOutputPreview } from "@/components/output-detail-content"
import type { OutputDetail } from "@/lib/api"

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
    const imagePayloadFact = preview.facts.find((fact) => fact.label === "Image payload")

    expect(imagePayloadFact?.value).toBe("bytes_v2")
    expect(preview.notes.join(" ")).toContain("training-ready bytes image payload")
  })
})
