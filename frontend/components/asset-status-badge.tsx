import type { IndexingStatus } from "@/lib/api";
import { formatIndexingStatus } from "@/lib/format";

import { Badge } from "@/components/ui/badge";

function getStatusClassName(status: IndexingStatus) {
  if (status === "indexed") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200";
  }

  if (status === "indexing") {
    return "border-sky-500/30 bg-sky-500/10 text-sky-900 dark:text-sky-200";
  }

  if (status === "failed") {
    return "";
  }

  return "border-border bg-muted text-muted-foreground";
}

export function AssetStatusBadge({ status }: { status: IndexingStatus }) {
  return (
    <Badge className={getStatusClassName(status)} variant={status === "failed" ? "destructive" : "outline"}>
      {formatIndexingStatus(status)}
    </Badge>
  );
}
