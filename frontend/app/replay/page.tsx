import { Suspense } from "react"

import {
  VisualizationPage,
  VisualizationPageFallback,
} from "@/features/replay/visualization-page"

export default function ReplayRoute() {
  return (
    <Suspense fallback={<VisualizationPageFallback />}>
      <VisualizationPage />
    </Suspense>
  )
}
