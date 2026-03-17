import { Suspense } from "react";

import { VisualizationPage, VisualizationPageFallback } from "@/components/visualization-page";

export default function VisualizeRoute() {
  return (
    <Suspense fallback={<VisualizationPageFallback />}>
      <VisualizationPage />
    </Suspense>
  );
}
