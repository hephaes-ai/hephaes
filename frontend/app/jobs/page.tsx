import { Suspense } from "react";

import { JobsPage, JobsPageFallback } from "./jobs-page";

export default function JobsRoute() {
  return (
    <Suspense fallback={<JobsPageFallback />}>
      <JobsPage />
    </Suspense>
  );
}
