import { redirect } from "next/navigation"

import {
  buildConversionCreateHref,
  buildConversionUseHref,
} from "@/lib/navigation"
import {
  resolveBackendUrl,
  type SavedConversionConfigSummaryResponse,
} from "@/lib/api"

export const dynamic = "force-dynamic"

function parseAssetIds(rawAssetIds: string | null | undefined) {
  return Array.from(
    new Set(
      (rawAssetIds ?? "")
        .split(",")
        .map((assetId) => assetId.trim())
        .filter(Boolean)
    )
  )
}

function appendSearchParams(
  searchParams: Record<string, string | string[] | undefined>,
  nextParams: URLSearchParams
) {
  for (const [key, value] of Object.entries(searchParams)) {
    if (Array.isArray(value)) {
      for (const item of value) {
        nextParams.append(key, item)
      }
      continue
    }

    if (typeof value === "string") {
      nextParams.set(key, value)
    }
  }
}

async function loadSavedConfigs() {
  try {
    const response = await fetch(resolveBackendUrl("/conversion-configs"), {
      cache: "no-store",
    })

    if (!response.ok) {
      return null
    }

    const payload =
      (await response.json()) as SavedConversionConfigSummaryResponse[]
    return Array.isArray(payload) ? payload : null
  } catch {
    return null
  }
}

export default async function ConversionRoute({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const params = await searchParams
  const nextParams = new URLSearchParams()
  appendSearchParams(params, nextParams)

  const assetIds = parseAssetIds(nextParams.get("asset_ids"))
  const from = nextParams.get("from")
  const conversionId = nextParams.get("conversion_id")?.trim() || null
  const sourceAssetId = nextParams.get("source_asset_id")?.trim() || null
  const savedConfigId = nextParams.get("saved_config_id")?.trim() || null
  const savedConfigs = await loadSavedConfigs()

  const nextHref =
    savedConfigs && savedConfigs.length > 0
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

  redirect(nextHref)
}
