import { Suspense } from "react";

import { ConversionPage, ConversionPageFallback } from "@/components/conversion-page";

export default function ConversionRoute() {
  return (
    <Suspense fallback={<ConversionPageFallback />}>
      <ConversionPage />
    </Suspense>
  );
}
