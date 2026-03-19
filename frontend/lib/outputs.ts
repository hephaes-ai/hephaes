import type { OutputDetail, OutputFormat, OutputsQuery } from "@/lib/api";

export function buildOutputsHref({
  assetId,
  availability,
  conversionId,
  format,
  outputId,
  search,
}: {
  assetId?: string | null;
  availability?: string | null;
  conversionId?: string | null;
  format?: string | null;
  outputId?: string | null;
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

  if (search?.trim()) {
    params.set("search", search.trim());
  }

  const query = params.toString();
  return query ? `/outputs?${query}` : "/outputs";
}

function matchesSearch(output: OutputDetail, normalizedSearch: string) {
  return [
    output.file_name,
    output.output_file,
    output.relative_path,
    output.conversion_id,
    output.job_id,
    ...output.asset_ids,
  ].some((value) => value.toLowerCase().includes(normalizedSearch));
}

export function filterOutputs(outputs: OutputDetail[] | undefined, query?: OutputsQuery | null) {
  if (!outputs) {
    return undefined;
  }

  const normalizedSearch = query?.search?.trim().toLowerCase() ?? "";
  const normalizedFormat = query?.format?.trim() as OutputFormat | undefined;
  const normalizedAssetId = query?.asset_id?.trim();
  const normalizedAvailability = query?.availability?.trim();
  const normalizedConversionId = query?.conversion_id?.trim();

  return outputs.filter((output) => {
    if (normalizedSearch && !matchesSearch(output, normalizedSearch)) {
      return false;
    }

    if (normalizedFormat && output.format !== normalizedFormat) {
      return false;
    }

    if (normalizedAssetId && !output.asset_ids.includes(normalizedAssetId)) {
      return false;
    }

    if (normalizedAvailability && output.availability !== normalizedAvailability) {
      return false;
    }

    if (normalizedConversionId && output.conversion_id !== normalizedConversionId) {
      return false;
    }

    return true;
  });
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
