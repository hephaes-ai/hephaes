import { Suspense } from "react";

import { JobDetailPage, JobDetailPageFallback } from "./job-detail-page";

export default async function JobDetailRoute({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;

  return (
    <Suspense fallback={<JobDetailPageFallback />}>
      <JobDetailPage jobId={jobId} />
    </Suspense>
  );
}
