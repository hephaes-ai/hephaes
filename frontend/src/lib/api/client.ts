import { apiBaseUrl } from "../config";

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

type RequestJsonOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  signal?: AbortSignal;
  json?: JsonValue | Record<string, unknown>;
};

type ErrorPayload = {
  detail?: string;
};

export class ApiError extends Error {
  status: number;

  detail: string | null;

  constructor(message: string, status: number, detail: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function joinUrl(pathname: string): string {
  const base = apiBaseUrl.replace(/\/+$/, "");
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return `${base}${path}`;
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return text.length > 0 ? text : null;
}

export async function requestJson<T>(pathname: string, options: RequestJsonOptions = {}): Promise<T> {
  const headers = new Headers();
  let body: string | undefined;

  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.json);
  }

  const response = await fetch(joinUrl(pathname), {
    method: options.method || "GET",
    headers,
    body,
    signal: options.signal,
  });

  const payload = await parseResponseBody(response);

  if (!response.ok) {
    const errorPayload = payload as ErrorPayload | string | null;
    const detail =
      typeof errorPayload === "string"
        ? errorPayload
        : errorPayload && typeof errorPayload.detail === "string"
          ? errorPayload.detail
          : null;

    throw new ApiError(detail || `Request failed with status ${response.status}`, response.status, detail);
  }

  return payload as T;
}
