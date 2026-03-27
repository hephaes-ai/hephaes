import {
  getErrorMessage,
  resolveBackendUrl,
  type SavedConversionConfigSummaryResponse,
} from "@/lib/api"
import {
  buildConversionCreateHref,
  buildConversionUseHref,
} from "@/lib/navigation"

export type ConversionEntryResolution =
  | {
      href: string
      status: "ready"
    }
  | {
      error: string
      status: "error"
    }

export function parseConversionAssetIds(
  rawAssetIds: string | null | undefined
) {
  return Array.from(
    new Set(
      (rawAssetIds ?? "")
        .split(",")
        .map((assetId) => assetId.trim())
        .filter(Boolean)
    )
  )
}

async function loadSavedConversionConfigs() {
  const response = await fetch(resolveBackendUrl("/conversion-configs"), {
    cache: "no-store",
  })

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}.`)
  }

  const payload = (await response.json()) as SavedConversionConfigSummaryResponse[]
  return Array.isArray(payload) ? payload : []
}

export async function resolveConversionEntry(
  searchParams: URLSearchParams
): Promise<ConversionEntryResolution> {
  const assetIds = parseConversionAssetIds(searchParams.get("asset_ids"))
  const from = searchParams.get("from")
  const conversionId = searchParams.get("conversion_id")?.trim() || null
  const sourceAssetId = searchParams.get("source_asset_id")?.trim() || null
  const savedConfigId = searchParams.get("saved_config_id")?.trim() || null

  try {
    const savedConfigs = await loadSavedConversionConfigs()

    const href =
      savedConfigs.length > 0
        ? buildConversionUseHref({
            assetIds,
            conversionId,
            from,
            savedConfigId:
              savedConfigs.find((config) => config.id === savedConfigId)?.id ??
              savedConfigs[0]?.id ??
              null,
            sourceAssetId,
          })
        : buildConversionCreateHref({
            assetIds,
            from,
            sourceAssetId,
          })

    return {
      href,
      status: "ready",
    }
  } catch (error) {
    return {
      error: getErrorMessage(error),
      status: "error",
    }
  }
}
