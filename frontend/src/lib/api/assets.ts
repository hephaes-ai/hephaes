import { requestJson } from "./client";
import type {
  AssetDetailResponse,
  AssetListItem,
  AssetRegistrationRequest,
  AssetRegistrationResponse,
} from "./types";

export function registerAsset(payload: AssetRegistrationRequest, signal?: AbortSignal) {
  return requestJson<AssetRegistrationResponse>("/assets/register", {
    method: "POST",
    signal,
    json: payload,
  });
}

export function listAssets(signal?: AbortSignal) {
  return requestJson<AssetListItem[]>("/assets", { signal });
}

export function getAsset(assetId: string, signal?: AbortSignal) {
  return requestJson<AssetDetailResponse>(`/assets/${assetId}`, { signal });
}
