import { Suspense } from "react";

import { OutputsPage, OutputsPageFallback } from "@/components/outputs-page";

export default function OutputsRoute() {
  return (
    <Suspense fallback={<OutputsPageFallback />}>
      <OutputsPage />
    </Suspense>
  );
}
