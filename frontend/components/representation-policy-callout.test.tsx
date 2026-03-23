import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { RepresentationPolicyCallout } from "@/components/representation-policy-callout"

describe("RepresentationPolicyCallout", () => {
  it("renders training-ready defaults when policy is absent", () => {
    render(
      <RepresentationPolicyCallout
        hasContractMetadata
        metadataError={null}
        outputContractLegacyMarker="legacy_list_image_payload"
        policy={null}
      />
    )

    expect(screen.getByText("Image payload contract")).toBeInTheDocument()
    expect(screen.getByText("Training-ready bytes payload")).toBeInTheDocument()
    expect(screen.getByText("bytes_v2")).toBeInTheDocument()
  })

  it("renders legacy warning when legacy contract is active", () => {
    render(
      <RepresentationPolicyCallout
        hasContractMetadata
        metadataError={null}
        outputContractLegacyMarker="legacy_list_image_payload"
        policy={{
          compatibility_markers: ["legacy_list_image_payload"],
          image_payload_contract: "legacy_list_v1",
          null_encoding: "presence_flag",
          output_format: "tfrecord",
          payload_encoding: "typed_features",
          policy_version: 1,
          requested_image_payload_contract: "legacy_list_v1",
          warnings: [],
        }}
      />
    )

    expect(screen.getByText("Legacy compatibility mode detected")).toBeInTheDocument()
  })
})
