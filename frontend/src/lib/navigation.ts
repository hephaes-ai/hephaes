export function buildAssetDetailHref(assetId: string, returnHref: string) {
  return `/assets/${assetId}?from=${encodeURIComponent(returnHref)}`;
}

export function buildJobDetailHref(jobId: string, returnHref: string) {
  return `/jobs/${jobId}?from=${encodeURIComponent(returnHref)}`;
}

export function buildOutputDetailHref(outputId: string, returnHref: string) {
  return `/outputs/${outputId}?from=${encodeURIComponent(returnHref)}`;
}

function buildConversionQuery({
  assetIds,
  conversionId,
  from,
  savedConfigId,
  sourceAssetId,
}: {
  assetIds: string[];
  conversionId?: string | null;
  from?: string | null;
  savedConfigId?: string | null;
  sourceAssetId?: string | null;
}) {
  const params = new URLSearchParams();

  const normalizedAssetIds = assetIds.map((assetId) => assetId.trim()).filter(Boolean);
  if (normalizedAssetIds.length > 0) {
    params.set("asset_ids", normalizedAssetIds.join(","));
  }

  if (conversionId?.trim()) {
    params.set("conversion_id", conversionId.trim());
  }

  if (savedConfigId?.trim()) {
    params.set("saved_config_id", savedConfigId.trim());
  }

  if (sourceAssetId?.trim()) {
    params.set("source_asset_id", sourceAssetId.trim());
  }

  if (from?.trim()) {
    params.set("from", from.trim());
  }

  return params.toString()
}

export function buildConversionHref({
  assetIds,
  conversionId,
  from,
  savedConfigId,
  sourceAssetId,
}: {
  assetIds: string[];
  conversionId?: string | null;
  from?: string | null;
  savedConfigId?: string | null;
  sourceAssetId?: string | null;
}) {
  const query = buildConversionQuery({
    assetIds,
    conversionId,
    from,
    savedConfigId,
    sourceAssetId,
  })
  return query ? `/convert?${query}` : "/convert";
}

export function buildConversionCreateHref({
  assetIds,
  from,
  sourceAssetId,
}: {
  assetIds: string[];
  from?: string | null;
  sourceAssetId?: string | null;
}) {
  const query = buildConversionQuery({
    assetIds,
    from,
    sourceAssetId,
  })
  return query ? `/convert/new?${query}` : "/convert/new"
}

export function buildConversionUseHref({
  assetIds,
  conversionId,
  from,
  savedConfigId,
  sourceAssetId,
}: {
  assetIds: string[];
  conversionId?: string | null;
  from?: string | null;
  savedConfigId?: string | null;
  sourceAssetId?: string | null;
}) {
  const query = buildConversionQuery({
    assetIds,
    conversionId,
    from,
    savedConfigId,
    sourceAssetId,
  })
  return query ? `/convert/use?${query}` : "/convert/use"
}

export function buildHref(
  pathname: string,
  params?: Record<string, string | null | undefined>,
) {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params ?? {})) {
    if (!value?.trim()) {
      continue;
    }

    searchParams.set(key, value.trim());
  }

  const query = searchParams.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function resolveReturnHref(from: string | null | undefined, fallbackHref: string) {
  if (!from) {
    return fallbackHref;
  }

  // Keep return navigation local to this app.
  if (!from.startsWith("/") || from.startsWith("//")) {
    return fallbackHref;
  }

  return from;
}
