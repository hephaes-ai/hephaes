import { Suspense } from "react";

import { InventoryPage, InventoryPageFallback } from "@/components/inventory-page";

export default function Page() {
  return (
    <Suspense fallback={<InventoryPageFallback />}>
      <InventoryPage />
    </Suspense>
  );
}
