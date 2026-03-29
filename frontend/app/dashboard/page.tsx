import { Suspense } from "react"

import {
  DashboardPage,
  DashboardPageFallback,
} from "@/features/dashboard/dashboard-page"

export default function DashboardRoute() {
  return (
    <Suspense fallback={<DashboardPageFallback />}>
      <DashboardPage />
    </Suspense>
  )
}
