import type { OutputDetail } from "@/lib/api";

export function buildOutputsHref({
  assetId,
  availability,
  conversionId,
  format,
  outputId,
  role,
  search,
}: {
  assetId?: string | null;
  availability?: string | null;
  conversionId?: string | null;
  format?: string | null;
  outputId?: string | null;
  role?: string | null;
  search?: string | null;
} = {}) {
  const params = new URLSearchParams();

  if (assetId?.trim()) {
    params.set("asset_id", assetId.trim());
  }

  if (availability?.trim()) {
    params.set("availability", availability.trim());
  }

  if (conversionId?.trim()) {
    params.set("conversion_id", conversionId.trim());
  }

  if (format?.trim()) {
    params.set("format", format.trim());
  }

  if (outputId?.trim()) {
    params.set("output", outputId.trim());
  }

  if (role?.trim()) {
    params.set("role", role.trim());
  }

  if (search?.trim()) {
    params.set("search", search.trim());
  }

  const query = params.toString();
  return query ? `/outputs?${query}` : "/outputs";
}

export function countOutputsByAsset(outputs: OutputDetail[] | undefined) {
  const counts = new Map<string, number>();

  for (const output of outputs ?? []) {
    for (const assetId of output.asset_ids) {
      counts.set(assetId, (counts.get(assetId) ?? 0) + 1);
    }
  }

  return counts;
}
