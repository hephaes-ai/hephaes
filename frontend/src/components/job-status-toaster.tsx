"use client";

import * as React from "react";

import { toast } from "@/components/ui/sonner";
import { useBackendCache, useJobs } from "@/hooks/use-backend";
import type { JobSummary } from "@/lib/api";
import { formatJobType, isWorkflowActiveStatus } from "@/lib/format";

function buildJobSuccessMessage(job: JobSummary) {
  if (job.type === "index") {
    return "Metadata extraction finished and the asset is ready to inspect.";
  }

  if (job.type === "convert") {
    return "Conversion outputs are ready to browse.";
  }

  return "The job finished successfully.";
}

export function JobStatusToaster() {
  const { revalidateAssetLists, revalidateConversions, revalidateJobs, revalidateOutputs } =
    useBackendCache();
  const jobsResponse = useJobs({ refreshInterval: 1500 });
  const knownStatusesRef = React.useRef<Map<string, string>>(new Map());

  React.useEffect(() => {
    const jobs = jobsResponse.data ?? [];
    if (jobs.length === 0) {
      return;
    }

    const knownStatuses = knownStatusesRef.current;

    for (const job of jobs) {
      const previousStatus = knownStatuses.get(job.id);

      if (previousStatus && previousStatus !== job.status) {
        const wasActive = isWorkflowActiveStatus(previousStatus as typeof job.status);
        const isActive = isWorkflowActiveStatus(job.status);

        if (wasActive && !isActive) {
          if (job.status === "succeeded") {
            toast.success(`${formatJobType(job.type)} finished`, {
              description: buildJobSuccessMessage(job),
            });
          } else if (job.status === "failed") {
            toast.error(`${formatJobType(job.type)} failed`, {
              description: job.error_message ?? "The backend reported a job failure.",
            });
          }

          void Promise.all([
            revalidateAssetLists(),
            revalidateConversions(),
            revalidateJobs(),
            revalidateOutputs(),
          ]);
        }
      }

      knownStatuses.set(job.id, job.status);
    }
  }, [jobsResponse.data, revalidateAssetLists, revalidateConversions, revalidateJobs, revalidateOutputs]);

  return null;
}
