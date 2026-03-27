import type { ConversionStatus, JobStatus, OutputActionStatus } from "@/lib/api";
import { formatWorkflowStatus, getWorkflowStatusClasses } from "@/lib/format";

import { Badge } from "@/components/ui/badge";

export function WorkflowStatusBadge({
  status,
}: {
  status: JobStatus | ConversionStatus | OutputActionStatus;
}) {
  return (
    <Badge
      className={getWorkflowStatusClasses(status)}
      variant={status === "failed" ? "destructive" : "outline"}
    >
      {formatWorkflowStatus(status)}
    </Badge>
  );
}
