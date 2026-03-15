import { requestJson } from "./client";
import type { HealthResponse } from "./types";

export function getHealth(signal?: AbortSignal) {
  return requestJson<HealthResponse>("/health", { signal });
}
