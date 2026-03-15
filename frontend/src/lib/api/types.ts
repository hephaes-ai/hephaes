export type IndexingStatus = "pending" | "indexing" | "indexed" | "failed";

export type HealthResponse = {
  status: string;
  app_name: string;
};

export type AssetSummary = {
  id: string;
  file_path: string;
  file_name: string;
  file_type: string;
  file_size: number;
  registered_time: string;
  indexing_status: IndexingStatus;
  last_indexed_time: string | null;
};

export type AssetListItem = AssetSummary;

export type AssetRegistrationRequest = {
  file_path: string;
};

export type AssetRegistrationResponse = AssetSummary;

export type AssetDetailResponse = {
  asset: AssetSummary;
};
