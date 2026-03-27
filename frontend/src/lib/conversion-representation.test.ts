import { describe, expect, it } from "vitest"

import {
  getImagePayloadContract,
  getPolicyVersion,
  isLegacyImagePayloadPolicy,
  normalizeOutputContractCapabilities,
} from "@/lib/conversion-representation"

describe("conversion representation helpers", () => {
  it("defaults to bytes_v2 when policy metadata is missing", () => {
    expect(getImagePayloadContract(null)).toBe("bytes_v2")
    expect(getPolicyVersion(null)).toBe(1)
  })

  it("detects legacy payload policy from explicit contract", () => {
    expect(
      isLegacyImagePayloadPolicy({
        compatibility_markers: [],
        image_payload_contract: "legacy_list_v1",
        null_encoding: "presence_flag",
        output_format: "tfrecord",
        payload_encoding: "typed_features",
        policy_version: 1,
        requested_image_payload_contract: "legacy_list_v1",
        warnings: [],
      })
    ).toBe(true)
  })

  it("normalizes output contract defaults for mixed-version responses", () => {
    const normalized = normalizeOutputContractCapabilities(null)
    expect(normalized.default_image_payload_contract).toBe("bytes_v2")
    expect(normalized.policy_version).toBe(1)
    expect(normalized.supported_image_payload_contracts).toEqual([
      "bytes_v2",
      "legacy_list_v1",
    ])
  })
})
