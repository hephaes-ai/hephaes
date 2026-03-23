import type {
  ConversionOutputContractCapabilities,
  ConversionRepresentationPolicy,
  TFRecordImagePayloadContract,
} from "@/lib/api"

export const DEFAULT_POLICY_VERSION = 1
export const LEGACY_COMPATIBILITY_MARKER = "legacy_list_image_payload"

export function getPolicyVersion(policy: ConversionRepresentationPolicy | null | undefined) {
  return policy?.policy_version ?? DEFAULT_POLICY_VERSION
}

export function getImagePayloadContract(
  policy: ConversionRepresentationPolicy | null | undefined,
  fallback: TFRecordImagePayloadContract = "bytes_v2"
) {
  return policy?.image_payload_contract ?? fallback
}

export function hasCompatibilityMarker(
  policy: ConversionRepresentationPolicy | null | undefined,
  marker: string
) {
  return Boolean(policy?.compatibility_markers?.includes(marker))
}

export function isLegacyImagePayloadPolicy(policy: ConversionRepresentationPolicy | null | undefined) {
  return (
    getImagePayloadContract(policy) === "legacy_list_v1" ||
    hasCompatibilityMarker(policy, LEGACY_COMPATIBILITY_MARKER)
  )
}

export function normalizeOutputContractCapabilities(
  outputContract: ConversionOutputContractCapabilities | null | undefined
): ConversionOutputContractCapabilities {
  return {
    default_image_payload_contract:
      outputContract?.default_image_payload_contract ?? "bytes_v2",
    legacy_compatibility_marker:
      outputContract?.legacy_compatibility_marker ?? LEGACY_COMPATIBILITY_MARKER,
    policy_version: outputContract?.policy_version ?? DEFAULT_POLICY_VERSION,
    supported_image_payload_contracts:
      outputContract?.supported_image_payload_contracts?.length
        ? outputContract.supported_image_payload_contracts
        : ["bytes_v2", "legacy_list_v1"],
  }
}

export function getPolicyWarnings(policy: ConversionRepresentationPolicy | null | undefined) {
  return policy?.warnings ?? []
}
