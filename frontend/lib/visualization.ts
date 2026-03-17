export interface VisualizationHrefOptions {
  assetId: string;
  episodeId?: string | null;
  from?: string | null;
}

export function buildVisualizeHref({ assetId, episodeId, from }: VisualizationHrefOptions) {
  const params = new URLSearchParams();
  params.set("asset_id", assetId);

  if (episodeId?.trim()) {
    params.set("episode_id", episodeId.trim());
  }

  if (from?.trim()) {
    params.set("from", from.trim());
  }

  const query = params.toString();
  return query ? `/visualize?${query}` : "/visualize";
}
