import type { ConversionStatus, JobStatus } from "@/lib/api";
import { formatWorkflowStatus } from "@/lib/format";

import { Badge } from "@/components/ui/badge";

function getWorkflowStatusClassName(status: JobStatus | ConversionStatus) {
  if (status === "succeeded") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200";
  }

  if (status === "running") {
    return "border-sky-500/30 bg-sky-500/10 text-sky-900 dark:text-sky-200";
  }

  if (status === "queued") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200";
  }

  return "";
}

export function WorkflowStatusBadge({
  status,
}: {
  status: JobStatus | ConversionStatus;
}) {
  return (
    <Badge
      className={getWorkflowStatusClassName(status)}
      variant={status === "failed" ? "destructive" : "outline"}
    >
      {formatWorkflowStatus(status)}
    </Badge>
  );
}
