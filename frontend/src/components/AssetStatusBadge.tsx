import type { IndexingStatus } from "../lib/api";

type AssetStatusBadgeProps = {
  status: IndexingStatus;
};

const STATUS_LABELS: Record<IndexingStatus, string> = {
  pending: "Unindexed",
  indexing: "Indexing",
  indexed: "Indexed",
  failed: "Failed",
};

export function AssetStatusBadge({ status }: AssetStatusBadgeProps) {
  const className =
    status === "indexed"
      ? "status-pill status-pill-success"
      : status === "failed"
        ? "status-pill status-pill-error"
        : "status-pill";

  return <span className={className}>{STATUS_LABELS[status]}</span>;
}
