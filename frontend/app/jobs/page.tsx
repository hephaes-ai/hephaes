import { Suspense } from "react"

import { JobsPage, JobsPageFallback } from "@/features/jobs/jobs-page"

export default function JobsRoute() {
  return (
    <Suspense fallback={<JobsPageFallback />}>
      <JobsPage />
    </Suspense>
  )
}
