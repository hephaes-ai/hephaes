export type AssetSelectionScope =
  | "all-assets"
  | "filtered-assets"
  | "search-results"
  | "selected-assets";

export interface SavedSearchDraft {
  id: string;
  label: string;
  query: {
    search?: string;
    status?: string;
    tag?: string;
    type?: string;
    sort?: string;
  };
}

export interface SavedSelectionDraft {
  id: string;
  label: string;
  assetIds: string[];
  scope: AssetSelectionScope;
}

export interface DatasetActionScope {
  scope: AssetSelectionScope;
  assetIds: string[];
}
