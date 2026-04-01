export type IndexingStatus = "pending" | "indexing" | "indexed" | "failed"
export type TopicModality = "image" | "points" | "scalar_series" | "other"
export type JobStatus = "queued" | "running" | "succeeded" | "failed"
export type JobType = "index" | "convert" | "prepare_visualization"
export type ConversionStatus = "queued" | "running" | "succeeded" | "failed"
export type ConversionFormat = "parquet" | "tfrecord"
export type OutputFormat =
  | "parquet"
  | "tfrecord"
  | "json"
  | "jsonl"
  | "unknown"
  | string
export type OutputAvailability = "ready" | "missing" | "invalid" | string
export type OutputRole = "dataset" | "manifest" | "sidecar" | string
export type ResampleMethod = "interpolate" | "downsample"
export type DecodeFailurePolicy = "skip" | "warn" | "fail"
export type TFRecordImagePayloadContract = "bytes_v2" | "legacy_list_v1"
export type ConversionRowStrategyKind = "trigger" | "per-message" | "resample"
export type ConversionFeatureSourceKind =
  | "path"
  | "constant"
  | "metadata"
  | "concat"
  | "stack"
export type ConversionTransformKind =
  | "cast"
  | "clamp"
  | "length"
  | "multi_hot"
  | "normalize"
  | "one_hot"
  | "scale"
  | "image_color_convert"
  | "image_crop"
  | "image_encode"
  | "image_resize"
export type ConversionSpec = Record<string, unknown>

export interface ConversionSpecDocument {
  metadata: Record<string, unknown>
  spec: ConversionSpec
  spec_version: number
}

export interface HealthResponse {
  app_name: string
  status: string
}

export interface DashboardCountEntry {
  count: number
  key: string
}

export interface DashboardTrendBucketResponse {
  count: number
  date: string
}

export interface DashboardInventorySummary {
  asset_count: number
  registered_last_24h: number
  registered_last_7d: number
  registered_last_30d: number
  total_asset_bytes: number
}

export interface DashboardIndexingSummary {
  status_counts: Record<IndexingStatus, number>
}

export interface DashboardJobsSummary {
  active_count: number
  failed_last_24h: number
  status_counts: Record<JobStatus, number>
}

export interface DashboardConversionsSummary {
  status_counts: Record<ConversionStatus, number>
}

export interface DashboardOutputsSummary {
  availability_counts: DashboardCountEntry[]
  format_counts: DashboardCountEntry[]
  output_count: number
  outputs_created_last_7d: number
  total_output_bytes: number
}

export interface DashboardFreshness {
  computed_at: string
  latest_asset_indexed_at: string | null
  latest_asset_registration_at: string | null
  latest_conversion_update_at: string | null
  latest_job_update_at: string | null
  latest_output_update_at: string | null
}

export interface DashboardSummaryResponse {
  conversions: DashboardConversionsSummary
  freshness: DashboardFreshness
  indexing: DashboardIndexingSummary
  inventory: DashboardInventorySummary
  jobs: DashboardJobsSummary
  outputs: DashboardOutputsSummary
}

export interface DashboardTrendsResponse {
  conversion_failures_by_day: DashboardTrendBucketResponse[]
  conversions_by_day: DashboardTrendBucketResponse[]
  days: number
  job_failures_by_day: DashboardTrendBucketResponse[]
  outputs_created_by_day: DashboardTrendBucketResponse[]
  registrations_by_day: DashboardTrendBucketResponse[]
}

export interface DashboardBlockersResponse {
  failed_assets: number
  failed_conversions: number
  failed_jobs: number
  invalid_outputs: number
  missing_outputs: number
  pending_assets: number
}

export interface AssetListQuery {
  max_duration?: number
  min_duration?: number
  search?: string
  start_after?: string
  start_before?: string
  status?: IndexingStatus
  tag?: string
  type?: string
}

export interface TagSummary {
  asset_count: number
  created_at: string
  id: string
  name: string
}

export interface AssetTag {
  created_at: string
  id: string
  name: string
}

export interface AssetSummary {
  file_name: string
  file_path: string
  file_size: number
  file_type: string
  id: string
  indexing_status: IndexingStatus
  last_indexed_time: string | null
  registered_time: string
  tags?: AssetTag[]
}

export interface IndexedTopicSummary {
  message_count: number
  message_type: string
  modality: TopicModality
  name: string
  rate_hz: number
}

export interface DefaultEpisodeSummary {
  duration: number
  episode_id: string
  label: string
}

export interface AssetMetadata {
  default_episode: DefaultEpisodeSummary | null
  duration: number | null
  end_time: string | null
  indexing_error: string | null
  message_count: number
  raw_metadata: Record<string, unknown>
  sensor_types: string[]
  start_time: string | null
  topic_count: number
  topics: IndexedTopicSummary[]
}

export interface AssetDetailResponse {
  asset: AssetSummary
  conversions: ConversionSummary[]
  metadata: AssetMetadata | null
  related_jobs: JobSummary[]
  tags: AssetTag[]
}

export interface AssetRegistrationRequest {
  file_path: string
}

export interface DirectoryScanRequest {
  directory_path: string
  recursive: boolean
}

export interface AssetRegistrationSkip {
  detail: string
  file_path: string
  reason: "duplicate" | "invalid_path"
}

export interface DirectoryScanResponse {
  discovered_file_count: number
  recursive: boolean
  registered_assets: AssetSummary[]
  scanned_directory: string
  skipped: AssetRegistrationSkip[]
}

export interface ReindexAllResponse {
  failed_assets: AssetSummary[]
  indexed_assets: AssetSummary[]
  total_requested: number
}

export interface TagCreateRequest {
  name: string
}

export interface AssetTagAttachRequest {
  tag_id: string
}

export interface ParquetConversionOutputRequest {
  compression?: "none" | "snappy" | "gzip" | "brotli" | "lz4" | "zstd"
  format: "parquet"
}

export interface TFRecordConversionOutputRequest {
  compression?: "none" | "gzip"
  format: "tfrecord"
  image_payload_contract?: TFRecordImagePayloadContract
  null_encoding?: "presence_flag"
  payload_encoding?: "typed_features"
}

export type ConversionOutputRequest =
  | ParquetConversionOutputRequest
  | TFRecordConversionOutputRequest

export interface ConversionResampleRequest {
  freq_hz: number
  method: ResampleMethod
}

export interface ConversionRepresentationPolicy {
  compatibility_markers: string[]
  image_payload_contract: TFRecordImagePayloadContract | null
  null_encoding: "presence_flag" | null
  output_format: ConversionFormat
  payload_encoding: "typed_features" | null
  policy_version: number
  requested_image_payload_contract: TFRecordImagePayloadContract | null
  warnings: string[]
}

export interface ConversionCreateRequest {
  asset_ids: string[]
  saved_config_id?: string | null
  spec?: ConversionSpec | null
  mapping?: Record<string, string[]> | null
  output?: ConversionOutputRequest | null
  resample?: ConversionResampleRequest | null
  write_manifest?: boolean | null
}

export interface ConversionCapabilities {
  spec_version: number
  supports_spec_documents: boolean
  supports_inspection: boolean
  supports_draft_generation: boolean
  supports_preview: boolean
  supports_migration: boolean
  row_strategies: ConversionRowStrategyKind[]
  authoring_row_strategies: ConversionRowStrategyKind[]
  planned_row_strategies: ConversionRowStrategyKind[]
  feature_source_kinds: ConversionFeatureSourceKind[]
  authoring_feature_source_kinds: ConversionFeatureSourceKind[]
  planned_feature_source_kinds: ConversionFeatureSourceKind[]
  feature_dtypes: string[]
  sync_policies: string[]
  missing_data_policies: string[]
  decode_failure_policies: DecodeFailurePolicy[]
  resample_strategies: ResampleMethod[]
  output_formats: ConversionFormat[]
  parquet_compressions: string[]
  tfrecord_compressions: string[]
  tfrecord_payload_encodings: string[]
  tfrecord_null_encodings: string[]
  transform_kinds: ConversionTransformKind[]
}

export interface ConversionAuthoringPersistenceCapabilities {
  mode: "sqlite-json"
  supports_saved_configs: boolean
  supports_saved_config_revisions: boolean
  supports_draft_revisions: boolean
  supports_preview_snapshots: boolean
  supports_migration_on_load: boolean
  supports_execute_from_saved_config: boolean
  spec_document_version: number
}

export interface ConversionOutputContractCapabilities {
  default_image_payload_contract: TFRecordImagePayloadContract
  legacy_compatibility_marker: string
  policy_version: number
  supported_image_payload_contracts: TFRecordImagePayloadContract[]
}

export interface ConversionAuthoringCapabilitiesResponse {
  authoring_api_version: number
  hephaes: ConversionCapabilities
  output_contract: ConversionOutputContractCapabilities
  persistence: ConversionAuthoringPersistenceCapabilities
}

export interface ConversionInspectionOptions {
  topics: string[]
  sample_n: number
  max_depth: number
  max_sequence_items: number
  on_failure: DecodeFailurePolicy
  topic_type_hints: Record<string, string>
}

export interface ConversionInspectionRequest extends ConversionInspectionOptions {
  asset_id: string
}

export interface SampledMessage {
  timestamp: number
  payload: unknown
}

export interface FieldCandidate {
  path: string
  kind: "scalar" | "sequence" | "struct" | "bytes" | "image" | "unknown"
  examples: unknown[]
  nullable: boolean
  candidate_dtypes: string[]
  shape_hint: number[] | null
  variable_length: boolean
  image_like: boolean
  confidence: number
  warnings: string[]
}

export interface TopicInspectionResult {
  topic: string
  message_type: string | null
  sampled_message_count: number
  sample_timestamps: number[]
  sample_payloads: SampledMessage[]
  top_level_summary: Record<string, unknown>
  field_candidates: Record<string, FieldCandidate>
  warnings: string[]
}

export interface InspectionResult {
  bag_path: string | null
  ros_version: string | null
  sample_n: number
  topics: Record<string, TopicInspectionResult>
  warnings: string[]
}

export interface ConversionInspectionResponse {
  asset_id: string
  request: ConversionInspectionRequest
  inspection: InspectionResult
  representation_policy?: ConversionRepresentationPolicy | null
}

export interface DraftSpecRequest {
  trigger_topic?: string | null
  selected_topics: string[]
  join_topics: string[]
  schema_name: string
  schema_version: number
  output_format: ConversionFormat
  output_compression: string
  max_features_per_topic: number
  label_feature?: string | null
  include_preview: boolean
  preview_rows: number
}

export interface PreviewRow {
  timestamp_ns: number
  field_data: Record<string, unknown>
  presence_data: Record<string, unknown>
}

export interface PreviewResult {
  rows: PreviewRow[]
  checked_records: number
  bad_records: number
}

export interface DraftSpecResult {
  request: DraftSpecRequest
  spec: ConversionSpec
  selected_topics: string[]
  trigger_topic: string | null
  join_topics: string[]
  warnings: string[]
  assumptions: string[]
  unresolved_fields: string[]
  preview: PreviewResult | null
}

export interface ConversionDraftRequest extends ConversionInspectionOptions {
  asset_id: string
  draft_request: DraftSpecRequest
}

export interface ConversionDraftResponse {
  asset_id: string
  request: ConversionDraftRequest
  inspection: InspectionResult
  draft: DraftSpecResult
  draft_revision_id: string | null
  representation_policy?: ConversionRepresentationPolicy | null
}

export interface ConversionPreviewRequest {
  asset_id: string
  spec: ConversionSpec
  sample_n: number
  topic_type_hints: Record<string, string>
}

export interface ConversionPreviewResponse {
  asset_id: string
  request: ConversionPreviewRequest
  preview: PreviewResult
  representation_policy?: ConversionRepresentationPolicy | null
}

export interface SavedConversionConfigCreateRequest {
  name: string
  description?: string | null
  metadata: Record<string, unknown>
  spec: ConversionSpec
}

export interface SavedConversionConfigUpdateRequest {
  name?: string | null
  description?: string | null
  metadata?: Record<string, unknown> | null
  spec?: ConversionSpec | null
}

export interface SavedConversionConfigDuplicateRequest {
  name?: string | null
  description?: string | null
  metadata?: Record<string, unknown> | null
}

export interface SavedConversionConfigRevisionResponse {
  id: string
  config_id: string
  revision_number: number
  change_kind: "create" | "update" | "duplicate" | "migration" | "import"
  change_summary: string | null
  spec_document_version: number
  spec_document_json: ConversionSpecDocument
  resolved_spec: ConversionSpec | null
  created_at: string
}

export interface SavedConversionDraftRevisionResponse {
  id: string
  saved_config_id: string | null
  revision_number: number
  source_asset_id: string | null
  status: "draft" | "saved" | "discarded"
  inspection_request: ConversionInspectionRequest
  inspection: InspectionResult
  draft_request: DraftSpecRequest
  draft_result: DraftSpecResult
  preview: PreviewResult | null
  created_at: string
  updated_at: string
}

export interface SavedConversionConfigSummaryResponse {
  id: string
  name: string
  description: string | null
  metadata: Record<string, unknown>
  spec_document_version: number
  spec_schema_name: string | null
  spec_schema_version: number | null
  spec_row_strategy_kind: string | null
  spec_output_format: string | null
  spec_output_compression: string | null
  spec_feature_count: number
  revision_count: number
  draft_count: number
  migration_notes: string[]
  invalid_reason: string | null
  latest_preview_available: boolean
  latest_preview_updated_at: string | null
  created_at: string
  updated_at: string
  last_opened_at: string | null
  status: "ready" | "needs_migration" | "invalid"
}

export interface SavedConversionConfigDetailResponse extends SavedConversionConfigSummaryResponse {
  spec_document_json: ConversionSpecDocument
  resolved_spec: ConversionSpec | null
  resolved_spec_document: ConversionSpecDocument | null
  latest_preview: PreviewResult | null
  revisions: SavedConversionConfigRevisionResponse[]
  draft_revisions: SavedConversionDraftRevisionResponse[]
}

export interface JobSummary {
  config_json: Record<string, unknown>
  created_at: string
  error_message: string | null
  finished_at: string | null
  id: string
  output_path: string | null
  representation_policy?: ConversionRepresentationPolicy | null
  started_at: string | null
  status: JobStatus
  target_asset_ids_json: string[]
  type: JobType
  updated_at: string
}

export interface ConversionSummary {
  asset_ids: string[]
  config: Record<string, unknown>
  created_at: string
  error_message: string | null
  id: string
  job_id: string
  output_path: string | null
  representation_policy?: ConversionRepresentationPolicy | null
  status: ConversionStatus
  updated_at: string
}

export interface ConversionDetail extends ConversionSummary {
  job: JobSummary
  output_files: string[]
}

export interface OutputsQuery {
  asset_id?: string
  availability?: OutputAvailability
  conversion_id?: string
  format?: OutputFormat
  limit?: number
  offset?: number
  role?: OutputRole
  search?: string
}

export interface OutputSummary {
  asset_ids: string[]
  conversion_id: string
  created_at: string
  content_url: string
  file_name: string
  format: OutputFormat
  id: string
  job_id: string
  media_type: string | null
  metadata: Record<string, unknown>
  relative_path: string
  role: OutputRole
  size_bytes: number
  updated_at: string
  availability_status: OutputAvailability
}

export interface OutputDetail extends OutputSummary {
  file_path?: string | null
}

export class BackendApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "BackendApiError"
    this.status = status
  }
}

const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000"

declare global {
  var __HEPHAES_BACKEND_BASE_URL__: string | undefined
}

export function getBackendBaseUrl() {
  const configuredDesktopBaseUrl =
    typeof globalThis !== "undefined"
      ? globalThis.__HEPHAES_BACKEND_BASE_URL__?.trim()
      : undefined
  const configuredNextBaseUrl =
    typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_BACKEND_BASE_URL?.trim()
      : undefined
  const resolvedBaseUrl =
    configuredDesktopBaseUrl ||
    configuredNextBaseUrl ||
    DEFAULT_BACKEND_BASE_URL
  return resolvedBaseUrl.replace(/\/+$/, "")
}

function buildBackendUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  return `${getBackendBaseUrl()}${normalizedPath}`
}

export function resolveBackendUrl(pathOrUrl: string) {
  if (/^https?:\/\//i.test(pathOrUrl)) {
    return pathOrUrl
  }

  return buildBackendUrl(pathOrUrl)
}

export function resolveBackendWebSocketUrl(pathOrUrl: string) {
  const resolvedUrl = new URL(resolveBackendUrl(pathOrUrl))
  resolvedUrl.protocol = resolvedUrl.protocol === "https:" ? "wss:" : "ws:"
  return resolvedUrl.toString()
}

function parseErrorDetail(payload: unknown, status: number) {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    if (typeof payload.detail === "string") {
      return payload.detail
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
            return item.msg
          }

          return JSON.stringify(item)
        })
        .join(" ")
    }
  }

  if (typeof payload === "string" && payload.trim().length > 0) {
    return payload
  }

  return `Request failed with status ${status}.`
}

function normalizeQueryValue(value: number | string | undefined) {
  if (value === undefined) {
    return null
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : null
  }

  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

export function serializeAssetListQuery(query?: AssetListQuery | null) {
  if (!query) {
    return ""
  }

  const params = new URLSearchParams()

  for (const [key, value] of Object.entries(query)) {
    const normalizedValue = normalizeQueryValue(value)
    if (normalizedValue) {
      params.set(key, normalizedValue)
    }
  }

  return params.toString()
}

export function serializeOutputsQuery(query?: OutputsQuery | null) {
  if (!query) {
    return ""
  }

  const params = new URLSearchParams()

  for (const [key, value] of Object.entries(query)) {
    const normalizedValue = normalizeQueryValue(value)
    if (normalizedValue) {
      params.set(key, normalizedValue)
    }
  }

  return params.toString()
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)

  if (typeof init?.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }

  const response = await fetch(buildBackendUrl(path), {
    ...init,
    headers,
  })

  const contentType = response.headers.get("Content-Type") ?? ""
  const rawPayload = await response.text()
  let payload: unknown = null

  if (rawPayload) {
    try {
      payload = JSON.parse(rawPayload)
    } catch {
      payload = rawPayload
    }
  }

  if (!response.ok) {
    throw new BackendApiError(
      parseErrorDetail(payload, response.status),
      response.status
    )
  }

  if (response.ok && rawPayload && !contentType.includes("application/json") && typeof payload === "string") {
    throw new BackendApiError(
      `Backend returned unexpected content type: ${contentType || "unknown"}. Is VITE_BACKEND_BASE_URL configured?`,
      response.status
    )
  }

  return payload as T
}

export function getErrorMessage(error: unknown) {
  if (error instanceof BackendApiError) {
    return error.message
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return "Something went wrong while talking to the backend."
}

export function getHealth() {
  return request<HealthResponse>("/health")
}

export function getDashboardSummary() {
  return request<DashboardSummaryResponse>("/dashboard/summary")
}

export function getDashboardTrends(days = 7) {
  const params = new URLSearchParams()
  params.set("days", String(days))
  return request<DashboardTrendsResponse>(
    `/dashboard/trends?${params.toString()}`
  )
}

export function getDashboardBlockers() {
  return request<DashboardBlockersResponse>("/dashboard/blockers")
}

export function listAssets(query?: AssetListQuery | null) {
  const queryString = serializeAssetListQuery(query)
  return request<AssetSummary[]>(
    queryString ? `/assets?${queryString}` : "/assets"
  )
}

export function getAssetDetail(assetId: string) {
  return request<AssetDetailResponse>(`/assets/${assetId}`)
}

export function indexAsset(assetId: string) {
  return request<AssetDetailResponse>(`/assets/${assetId}/index`, {
    method: "POST",
  })
}

export function reindexAllAssets() {
  return request<ReindexAllResponse>("/assets/reindex-all", {
    method: "POST",
  })
}

export function listTags() {
  return request<TagSummary[]>("/tags")
}

export function createTag(payload: TagCreateRequest) {
  return request<TagSummary>("/tags", {
    body: JSON.stringify(payload),
    method: "POST",
  })
}

export function attachTagToAsset(
  assetId: string,
  payload: AssetTagAttachRequest
) {
  return request<AssetDetailResponse>(`/assets/${assetId}/tags`, {
    body: JSON.stringify(payload),
    method: "POST",
  })
}

export function removeTagFromAsset(assetId: string, tagId: string) {
  return request<AssetDetailResponse>(`/assets/${assetId}/tags/${tagId}`, {
    method: "DELETE",
  })
}

export function registerAsset(payload: AssetRegistrationRequest) {
  return request<AssetSummary>("/assets/register", {
    body: JSON.stringify(payload),
    method: "POST",
  })
}

export function uploadAssetFile(file: File) {
  const headers = new Headers({
    "X-File-Name": file.name,
  })

  if (file.type) {
    headers.set("Content-Type", file.type)
  }

  return request<AssetSummary>("/assets/upload", {
    body: file,
    headers,
    method: "POST",
  })
}

export function scanDirectoryForAssets(payload: DirectoryScanRequest) {
  return request<DirectoryScanResponse>("/assets/scan-directory", {
    body: JSON.stringify(payload),
    method: "POST",
  })
}

export function createConversion(payload: ConversionCreateRequest) {
  return request<ConversionDetail>("/conversions", {
    body: JSON.stringify(payload),
    method: "POST",
  })
}

export function getConversionAuthoringCapabilities() {
  return request<ConversionAuthoringCapabilitiesResponse>(
    "/conversions/capabilities"
  )
}

export function inspectConversion(payload: ConversionInspectionRequest) {
  return request<ConversionInspectionResponse>("/conversions/inspect", {
    body: JSON.stringify(payload),
    method: "POST",
  })
}

export function draftConversion(payload: ConversionDraftRequest) {
  return request<ConversionDraftResponse>("/conversions/draft", {
    body: JSON.stringify(payload),
    method: "POST",
  })
}

export function previewConversion(payload: ConversionPreviewRequest) {
  return request<ConversionPreviewResponse>("/conversions/preview", {
    body: JSON.stringify(payload),
    method: "POST",
  })
}

export function listConversions() {
  return request<ConversionSummary[]>("/conversions")
}

export function getConversion(conversionId: string) {
  return request<ConversionDetail>(`/conversions/${conversionId}`)
}

export function listConversionConfigs() {
  return request<SavedConversionConfigSummaryResponse[]>("/conversion-configs")
}

export function getConversionConfig(configId: string) {
  return request<SavedConversionConfigDetailResponse>(
    `/conversion-configs/${configId}`
  )
}

export function createConversionConfig(
  payload: SavedConversionConfigCreateRequest
) {
  return request<SavedConversionConfigDetailResponse>("/conversion-configs", {
    body: JSON.stringify(payload),
    method: "POST",
  })
}

export function updateConversionConfig(
  configId: string,
  payload: SavedConversionConfigUpdateRequest
) {
  return request<SavedConversionConfigDetailResponse>(
    `/conversion-configs/${configId}`,
    {
      body: JSON.stringify(payload),
      method: "PATCH",
    }
  )
}

export function duplicateConversionConfig(
  configId: string,
  payload: SavedConversionConfigDuplicateRequest
) {
  return request<SavedConversionConfigDetailResponse>(
    `/conversion-configs/${configId}/duplicate`,
    {
      body: JSON.stringify(payload),
      method: "POST",
    }
  )
}

export function listOutputs(query?: OutputsQuery | null) {
  const queryString = serializeOutputsQuery({
    limit: query?.limit ?? 500,
    ...query,
  })

  return request<OutputDetail[]>(
    queryString ? `/outputs?${queryString}` : "/outputs"
  )
}

export function getOutput(outputId: string) {
  return request<OutputDetail>(`/outputs/${outputId}`)
}

export function listJobs() {
  return request<JobSummary[]>("/jobs")
}

export function getJob(jobId: string) {
  return request<JobSummary>(`/jobs/${jobId}`)
}
