export type IndexingStatus = "pending" | "indexing" | "indexed" | "failed";
export type TopicModality = "image" | "points" | "scalar_series" | "other";
export type JobStatus = "queued" | "running" | "succeeded" | "failed";
export type JobType = "index" | "convert" | "prepare_visualization";
export type ConversionStatus = "queued" | "running" | "succeeded" | "failed";
export type ConversionFormat = "parquet" | "tfrecord";
export type OutputFormat = "parquet" | "tfrecord" | "json" | "jsonl" | "unknown" | string;
export type OutputAvailability = "ready" | "missing" | "invalid" | string;
export type OutputRole = "dataset" | "manifest" | "sidecar" | string;
export type OutputActionType = "refresh_metadata" | "vlm_tagging" | string;
export type OutputActionStatus = "queued" | "running" | "succeeded" | "failed";
export type ResampleMethod = "interpolate" | "downsample";

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
  asset_count: number;
  created_at: string;
  id: string;
  name: string;
}

export interface AssetTag {
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
  tags?: AssetTag[];
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

export interface EpisodeSummary {
  default_lane_count: number;
  duration: number;
  end_time: string | null;
  episode_id: string;
  has_visualizable_streams: boolean;
  label: string;
  start_time: string | null;
}

export interface EpisodeDetailResponse {
  default_lane_count: number;
  duration: number;
  end_time: string | null;
  episode_id: string;
  has_visualizable_streams: boolean;
  label: string;
  start_time: string | null;
  topic_count?: number | null;
}

export type ViewerSourceStatus = "none" | "preparing" | "ready" | "failed";
export type ViewerSourceKind = "rrd_url" | "grpc_url";

export interface EpisodeViewerSourceResponse {
  artifact_path: string | null;
  episode_id: string;
  error_message: string | null;
  job_id: string | null;
  recording_version: string | null;
  source_kind: ViewerSourceKind | null;
  source_url: string | null;
  status: ViewerSourceStatus;
  updated_at: string | null;
  viewer_version: string | null;

  // Backward-compatible optional fields from earlier frontend contract versions.
  detail?: string | null;
  preparation_job_id?: string | null;
}

export interface PrepareVisualizationResponse {
  job: JobSummary;
}

export interface EpisodeTimelineEvent {
  count?: number;
  timestamp_ns: number;
}

export interface EpisodeTimelineBucket {
  bucket_index: number;
  end_offset_ns: number;
  event_count: number;
  start_offset_ns: number;
}

export interface EpisodeTimelineLane {
  buckets?: EpisodeTimelineBucket[];
  events: EpisodeTimelineEvent[];
  label: string;
  modality: TopicModality;
  source_topic?: string;
  stream_key?: string;
  stream_id: string;
}

export interface EpisodeTimelineResponse {
  duration_ns: number;
  end_timestamp_ns?: number | null;
  end_time_ns?: number;
  episode_id: string;
  lanes: EpisodeTimelineLane[];
  start_timestamp_ns?: number | null;
  start_time_ns?: number;
}

export interface EpisodeSamplesQuery {
  stream_ids?: string[];
  timestamp_ns: number;
  window_after_ns?: number;
  window_before_ns?: number;
}

export interface EpisodeSample {
  message_type?: string;
  metadata?: Record<string, unknown>;
  metadata_json?: Record<string, unknown>;
  modality: TopicModality;
  payload: Record<string, unknown> | null;
  selection_strategy?: "nearest" | "window";
  stream_id: string;
  timestamp_ns: number;
  topic_name?: string;
}

export interface EpisodeStreamSamplesResponse {
  modality: TopicModality;
  sample_count: number;
  samples: EpisodeSample[];
  selection_strategy: "nearest" | "window";
  source_topic: string;
  stream_id: string;
  stream_key: string;
}

export interface EpisodeSamplesResponse {
  requested_timestamp_ns?: number;
  streams?: EpisodeStreamSamplesResponse[];
  episode_id: string;
  samples: EpisodeSample[];
  timestamp_ns: number;
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
  conversions: ConversionSummary[];
  episodes: EpisodeSummary[];
  metadata: AssetMetadata | null;
  related_jobs: JobSummary[];
  tags: AssetTag[];
}

export interface AssetRegistrationRequest {
  file_path: string;
}

export interface DirectoryScanRequest {
  directory_path: string;
  recursive: boolean;
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

export interface DirectoryScanResponse {
  discovered_file_count: number;
  recursive: boolean;
  registered_assets: AssetSummary[];
  scanned_directory: string;
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

export interface ParquetConversionOutputRequest {
  compression?: "none" | "snappy" | "gzip" | "brotli" | "lz4" | "zstd";
  format: "parquet";
}

export interface TFRecordConversionOutputRequest {
  compression?: "none" | "gzip";
  format: "tfrecord";
  null_encoding?: "presence_flag";
  payload_encoding?: "typed_features";
}

export type ConversionOutputRequest =
  | ParquetConversionOutputRequest
  | TFRecordConversionOutputRequest;

export interface ConversionResampleRequest {
  freq_hz: number;
  method: ResampleMethod;
}

export interface ConversionCreateRequest {
  asset_ids: string[];
  mapping?: Record<string, string[]> | null;
  output: ConversionOutputRequest;
  resample?: ConversionResampleRequest | null;
  write_manifest?: boolean;
}

export interface JobSummary {
  config_json: Record<string, unknown>;
  created_at: string;
  error_message: string | null;
  finished_at: string | null;
  id: string;
  output_path: string | null;
  started_at: string | null;
  status: JobStatus;
  target_asset_ids_json: string[];
  type: JobType;
  updated_at: string;
}

export interface ConversionSummary {
  asset_ids: string[];
  config: Record<string, unknown>;
  created_at: string;
  error_message: string | null;
  id: string;
  job_id: string;
  output_path: string | null;
  status: ConversionStatus;
  updated_at: string;
}

export interface ConversionDetail extends ConversionSummary {
  job: JobSummary;
  output_files: string[];
}

export interface OutputsQuery {
  asset_id?: string;
  availability?: OutputAvailability;
  conversion_id?: string;
  format?: OutputFormat;
  limit?: number;
  offset?: number;
  role?: OutputRole;
  search?: string;
}

export interface OutputSummary {
  asset_ids: string[];
  conversion_id: string;
  created_at: string;
  content_url: string;
  file_name: string;
  format: OutputFormat;
  id: string;
  job_id: string;
  latest_action: OutputActionSummary | null;
  media_type: string | null;
  metadata: Record<string, unknown>;
  relative_path: string;
  role: OutputRole;
  size_bytes: number;
  updated_at: string;
  availability_status: OutputAvailability;
}

export interface OutputDetail extends OutputSummary {
  file_path?: string | null;
}

export interface CreateOutputActionRequest {
  action_type: OutputActionType;
  config: Record<string, unknown>;
}

export interface OutputActionSummary {
  action_type: OutputActionType;
  config: Record<string, unknown>;
  created_at: string;
  error_message: string | null;
  finished_at: string | null;
  id: string;
  output_id: string;
  output_path: string | null;
  result: Record<string, unknown>;
  started_at: string | null;
  status: OutputActionStatus;
  updated_at: string;
}

export interface OutputActionDetail extends OutputActionSummary {
  output_file_path?: string | null;
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

export function resolveBackendUrl(pathOrUrl: string) {
  if (/^https?:\/\//i.test(pathOrUrl)) {
    return pathOrUrl;
  }

  return buildBackendUrl(pathOrUrl);
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

export function serializeOutputsQuery(query?: OutputsQuery | null) {
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

  if (typeof init?.body === "string" && !headers.has("Content-Type")) {
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

export function uploadAssetFile(file: File) {
  const headers = new Headers({
    "X-File-Name": file.name,
  });

  if (file.type) {
    headers.set("Content-Type", file.type);
  }

  return request<AssetSummary>("/assets/upload", {
    body: file,
    headers,
    method: "POST",
  });
}

export function registerAssetsFromDialog() {
  return request<DialogAssetRegistrationResponse>("/assets/register-dialog", {
    method: "POST",
  });
}

export function scanDirectoryForAssets(payload: DirectoryScanRequest) {
  return request<DirectoryScanResponse>("/assets/scan-directory", {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export function createConversion(payload: ConversionCreateRequest) {
  return request<ConversionDetail>("/conversions", {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export function listConversions() {
  return request<ConversionSummary[]>("/conversions");
}

export function getConversion(conversionId: string) {
  return request<ConversionDetail>(`/conversions/${conversionId}`);
}

export function listOutputs(query?: OutputsQuery | null) {
  const queryString = serializeOutputsQuery({
    limit: query?.limit ?? 500,
    ...query,
  });

  return request<OutputDetail[]>(queryString ? `/outputs?${queryString}` : "/outputs");
}

export function getOutput(outputId: string) {
  return request<OutputDetail>(`/outputs/${outputId}`);
}

export function listOutputActions(outputId: string) {
  return request<OutputActionDetail[]>(`/outputs/${outputId}/actions`);
}

export function getOutputAction(actionId: string) {
  return request<OutputActionDetail>(`/outputs/actions/${actionId}`);
}

export function createOutputAction(outputId: string, payload: CreateOutputActionRequest) {
  return request<OutputActionDetail>(`/outputs/${outputId}/actions`, {
    body: JSON.stringify(payload),
    method: "POST",
  });
}

export function listJobs() {
  return request<JobSummary[]>("/jobs");
}

export function getJob(jobId: string) {
  return request<JobSummary>(`/jobs/${jobId}`);
}

export function listAssetEpisodes(assetId: string) {
  return request<EpisodeSummary[]>(`/assets/${assetId}/episodes`);
}

export function getAssetEpisode(assetId: string, episodeId: string) {
  return request<EpisodeDetailResponse>(`/assets/${assetId}/episodes/${episodeId}`);
}

export function getEpisodeViewerSource(assetId: string, episodeId: string) {
  return request<EpisodeViewerSourceResponse>(`/assets/${assetId}/episodes/${episodeId}/viewer-source`);
}

export function prepareEpisodeVisualization(assetId: string, episodeId: string) {
  return request<PrepareVisualizationResponse>(`/assets/${assetId}/episodes/${episodeId}/prepare-visualization`, {
    method: "POST",
  });
}

export function getEpisodeTimeline(assetId: string, episodeId: string) {
  return request<EpisodeTimelineResponse>(`/assets/${assetId}/episodes/${episodeId}/timeline`);
}

export function getEpisodeSamples(assetId: string, episodeId: string, query: EpisodeSamplesQuery) {
  const params = new URLSearchParams();
  params.set("timestamp_ns", String(query.timestamp_ns));

  if (query.window_before_ns !== undefined) {
    params.set("window_before_ns", String(query.window_before_ns));
  }

  if (query.window_after_ns !== undefined) {
    params.set("window_after_ns", String(query.window_after_ns));
  }

  for (const streamId of query.stream_ids ?? []) {
    const normalized = streamId.trim();
    if (normalized) {
      params.append("stream_ids", normalized);
    }
  }

  const queryString = params.toString();
  return request<EpisodeSamplesResponse>(`/assets/${assetId}/episodes/${episodeId}/samples?${queryString}`);
}
