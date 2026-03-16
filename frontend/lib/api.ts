export type IndexingStatus = "pending" | "indexing" | "indexed" | "failed";

export interface HealthResponse {
  app_name: string;
  status: string;
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
}

export interface AssetDetailResponse {
  asset: AssetSummary;
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
  if (
    typeof payload === "object" &&
    payload !== null &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }

  if (typeof payload === "string" && payload.trim().length > 0) {
    return payload;
  }

  return `Request failed with status ${status}.`;
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

export function listAssets() {
  return request<AssetSummary[]>("/assets");
}

export function getAssetDetail(assetId: string) {
  return request<AssetDetailResponse>(`/assets/${assetId}`);
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
