export interface ReplayHrefOptions {
  assetId: string;
  episodeId?: string | null;
  from?: string | null;
}

export function buildReplayHref({ assetId, episodeId, from }: ReplayHrefOptions) {
  const params = new URLSearchParams();
  params.set("asset_id", assetId);

  if (episodeId?.trim()) {
    params.set("episode_id", episodeId.trim());
  }

  if (from?.trim()) {
    params.set("from", from.trim());
  }

  const query = params.toString();
  return query ? `/replay?${query}` : "/replay";
}

export const buildVisualizeHref = buildReplayHref;
