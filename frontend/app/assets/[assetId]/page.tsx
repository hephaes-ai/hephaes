import { Suspense } from "react"

import {
  AssetDetailPage,
  AssetDetailPageFallback,
} from "@/features/assets/asset-detail-page"

interface AssetPageProps {
  params: Promise<{
    assetId: string
  }>
}

export default async function Page({ params }: AssetPageProps) {
  const { assetId } = await params

  return (
    <Suspense fallback={<AssetDetailPageFallback />}>
      <AssetDetailPage assetId={assetId} />
    </Suspense>
  )
}
