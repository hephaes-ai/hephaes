import { Suspense } from "react"

import {
  OutputDetailPage,
  OutputDetailPageFallback,
} from "@/features/outputs/output-detail-page"

interface OutputDetailRouteProps {
  params: Promise<{ outputId: string }>
}

export default async function Page({ params }: OutputDetailRouteProps) {
  const { outputId } = await params

  return (
    <Suspense fallback={<OutputDetailPageFallback />}>
      <OutputDetailPage outputId={outputId} />
    </Suspense>
  )
}
