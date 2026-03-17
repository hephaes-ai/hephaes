export type IndexingStatus = "pending" | "indexing" | "indexed" | "failed";
export type TopicModality = "image" | "points" | "scalar_series" | "other";

export interface HealthResponse {
  app_name: string;
  status: string;
}

export interface AssetListQuery {
  max_duration?: number;
  min_duration?: number;
  search?: string;
  start_after?: string;
  start_before?: string;
  status?: IndexingStatus;
  tag?: string;
  type?: string;
}

export interface TagSummary {
  created_at: string;
  id: string;
  name: string;
}

export interface AssetSummary {
  file_name: string;
  file_path: string;
  file_size: number;
  file_type: string;
  id: string;
  indexing_status: IndexingStatus;
  last_indexed_time: string | null;
  registered_time: string;
  tags?: TagSummary[];
}

export interface IndexedTopicSummary {
  message_count: number;
  message_type: string;
  modality: TopicModality;
  name: string;
  rate_hz: number;
}

export interface DefaultEpisodeSummary {
  duration: number;
  episode_id: string;
  label: string;
}

export interface VisualizationSummary {
  default_lane_count: number;
  has_visualizable_streams: boolean;
}

export interface AssetMetadata {
  default_episode: DefaultEpisodeSummary | null;
  duration: number | null;
  end_time: string | null;
  indexing_error: string | null;
  message_count: number;
  raw_metadata: Record<string, unknown>;
  sensor_types: string[];
  start_time: string | null;
  topic_count: number;
  topics: IndexedTopicSummary[];
  visualization_summary: VisualizationSummary | null;
}

export interface AssetDetailResponse {
  asset: AssetSummary;
  metadata: AssetMetadata | null;
  tags: TagSummary[];
}

export interface AssetRegistrationRequest {
  file_path: string;
}

export interface AssetRegistrationSkip {
  detail: string;
  file_path: string;
  reason: "duplicate" | "invalid_path";
}

export interface DialogAssetRegistrationResponse {
  canceled: boolean;
  registered_assets: AssetSummary[];
  skipped: AssetRegistrationSkip[];
}

export interface ReindexAllResponse {
  failed_assets: AssetSummary[];
  indexed_assets: AssetSummary[];
  total_requested: number;
}

export interface TagCreateRequest {
  name: string;
}

export interface AssetTagAttachRequest {
  tag_id: string;
}

export class BackendApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "BackendApiError";
    this.status = status;
  }
}

const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000";

function getBackendBaseUrl() {
  const configuredBaseUrl = process.env.NEXT_PUBLIC_BACKEND_BASE_URL?.trim();
  const resolvedBaseUrl = configuredBaseUrl || DEFAULT_BACKEND_BASE_URL;
  return resolvedBaseUrl.replace(/\/+$/, "");
}

function buildBackendUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getBackendBaseUrl()}${normalizedPath}`;
}

function parseErrorDetail(payload: unknown, status: number) {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    if (typeof payload.detail === "string") {
      return payload.detail;
    }

    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => {
          if (
            typeof item === "object" &&
            item !== null &&
            "msg" in item &&
            typeof item.msg === "string"
          ) {
            return item.msg;
          }

          return JSON.stringify(item);
        })
        .join(" ");
    }
  }

  if (typeof payload === "string" && payload.trim().length > 0) {
    return payload;
  }

  return `Request failed with status ${status}.`;
}

function normalizeQueryValue(value: number | string | undefined) {
  if (value === undefined) {
    return null;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : null;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function serializeAssetListQuery(query?: AssetListQuery | null) {
  if (!query) {
    return "";
  }

  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    const normalizedValue = normalizeQueryValue(value);
    if (normalizedValue) {
      params.set(key, normalizedValue);
    }
  }

  return params.toString();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);

  if (init?.body !== undefined && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildBackendUrl(path), {
    ...init,
    headers,
  });

  const rawPayload = await response.text();
  let payload: unknown = null;

  if (rawPayload) {
    try {
      payload = JSON.parse(rawPayload);
    } catch {
      payload = rawPayload;
    }
  }

  if (!response.ok) {
    throw new BackendApiError(parseErrorDetail(payload, response.status), response.status);
  }

  return payload as T;
}

export function getErrorMessage(error: unknown) {
  if (error instanceof BackendApiError) {
    return error.message;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Something went wrong while talking to the backend.";
}

export function getHealth() {
  return request<HealthResponse>("/health");
}

export function listAssets(query?: AssetListQuery | null) {
  const queryString = serializeAssetListQuery(query);
  return request<AssetSummary[]>(queryString ? `/assets?${queryString}` : "/assets");
}

export function getAssetDetail(assetId: string) {
  return request<AssetDetailResponse>(`/assets/${assetId}`);
}

export function indexAsset(assetId: string) {
  return request<AssetDetailResponse>(`/assets/${assetId}/index`, {
    method: "POST",
  });
}

export function reindexAllAssets() {
  return request<ReindexAllResponse>("/assets/reindex-all", {
    method: "POST",
  });
}

export function listTags() {
  return request<TagSummary[]>("/tags");
}

export function createTag(payload: TagCreateRequest) {
  return request<TagSummary>("/tags", {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export function attachTagToAsset(assetId: string, payload: AssetTagAttachRequest) {
  return request<AssetDetailResponse>(`/assets/${assetId}/tags`, {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export function removeTagFromAsset(assetId: string, tagId: string) {
  return request<AssetDetailResponse>(`/assets/${assetId}/tags/${tagId}`, {
    method: "DELETE",
  });
}

export function registerAsset(payload: AssetRegistrationRequest) {
  return request<AssetSummary>("/assets/register", {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export function registerAssetsFromDialog() {
  return request<DialogAssetRegistrationResponse>("/assets/register-dialog", {
    method: "POST",
  });
}
