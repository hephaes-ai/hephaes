import { Suspense } from "react"

import {
  OutputsPage,
  OutputsPageFallback,
} from "@/features/outputs/outputs-page"

export default function OutputsRoute() {
  return (
    <Suspense fallback={<OutputsPageFallback />}>
      <OutputsPage />
    </Suspense>
  )
}
