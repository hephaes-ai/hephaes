import { describe, expect, it } from "vitest"

import { buildOutputsHref } from "@/lib/outputs"

describe("buildOutputsHref", () => {
  it("keeps image payload contract context in deep links", () => {
    const href = buildOutputsHref({
      conversionId: "conv-1",
      imagePayloadContract: "bytes_v2",
    })

    expect(href).toContain("conversion_id=conv-1")
    expect(href).toContain("image_payload_contract=bytes_v2")
  })
})
