import * as React from "react"
import { Navigate, Route, Routes, useParams } from "react-router-dom"

import {
  AssetDetailPage,
  AssetDetailPageFallback,
} from "../../app/assets/[assetId]/asset-detail-page"
import {
  ConversionAuthoringWorkspace,
  ConversionAuthoringWorkspaceFallback,
} from "../../app/convert/conversion-authoring-workspace"
import {
  DashboardPage,
  DashboardPageFallback,
} from "../../app/dashboard/dashboard-page"
import {
  InventoryPage,
  InventoryPageFallback,
} from "../../app/inventory/inventory-page"
import {
  JobDetailPage,
  JobDetailPageFallback,
} from "../../app/jobs/[jobId]/job-detail-page"
import { JobsPage, JobsPageFallback } from "../../app/jobs/jobs-page"
import {
  OutputDetailPage,
  OutputDetailPageFallback,
} from "../../app/outputs/[outputId]/output-detail-page"
import {
  OutputsPage,
  OutputsPageFallback,
} from "../../app/outputs/outputs-page"
import {
  VisualizationPage,
  VisualizationPageFallback,
} from "../../app/replay/visualization-page"

import { ConversionEntryErrorState } from "@/components/conversion-entry-state"
import { resolveConversionEntry } from "@/lib/conversion-entry"
import { useAppRouter, useAppSearchParams } from "@/lib/app-routing"
import { resolveReturnHref } from "@/lib/navigation"

function HomeRedirectRoute() {
  const searchParams = useAppSearchParams()
  const query = searchParams.toString()

  return <Navigate replace to={query ? `/inventory?${query}` : "/dashboard"} />
}

function VisualizeRedirectRoute() {
  const searchParams = useAppSearchParams()
  const query = searchParams.toString()

  return <Navigate replace to={query ? `/replay?${query}` : "/replay"} />
}

function DashboardRoute() {
  return (
    <React.Suspense fallback={<DashboardPageFallback />}>
      <DashboardPage />
    </React.Suspense>
  )
}

function InventoryRoute() {
  return (
    <React.Suspense fallback={<InventoryPageFallback />}>
      <InventoryPage />
    </React.Suspense>
  )
}

function AssetDetailRoute() {
  const params = useParams<{ assetId: string }>()
  const assetId = params.assetId?.trim()

  if (!assetId) {
    return <Navigate replace to="/inventory" />
  }

  return (
    <React.Suspense fallback={<AssetDetailPageFallback />}>
      <AssetDetailPage assetId={assetId} />
    </React.Suspense>
  )
}

function JobsRoute() {
  return (
    <React.Suspense fallback={<JobsPageFallback />}>
      <JobsPage />
    </React.Suspense>
  )
}

function JobDetailRoute() {
  const params = useParams<{ jobId: string }>()
  const jobId = params.jobId?.trim()

  if (!jobId) {
    return <Navigate replace to="/jobs" />
  }

  return (
    <React.Suspense fallback={<JobDetailPageFallback />}>
      <JobDetailPage jobId={jobId} />
    </React.Suspense>
  )
}

function OutputsRoute() {
  return (
    <React.Suspense fallback={<OutputsPageFallback />}>
      <OutputsPage />
    </React.Suspense>
  )
}

function OutputDetailRoute() {
  const params = useParams<{ outputId: string }>()
  const outputId = params.outputId?.trim()

  if (!outputId) {
    return <Navigate replace to="/outputs" />
  }

  return (
    <React.Suspense fallback={<OutputDetailPageFallback />}>
      <OutputDetailPage outputId={outputId} />
    </React.Suspense>
  )
}

function ReplayRoute() {
  return (
    <React.Suspense fallback={<VisualizationPageFallback />}>
      <VisualizationPage />
    </React.Suspense>
  )
}

function ConversionBootstrapRoute() {
  const router = useAppRouter()
  const searchParams = useAppSearchParams()
  const queryString = searchParams.toString()
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null)
  const returnHref = resolveReturnHref(searchParams.get("from"), "/inventory")

  React.useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      setErrorMessage(null)
      const resolution = await resolveConversionEntry(
        new URLSearchParams(queryString)
      )

      if (cancelled) {
        return
      }

      if (resolution.status === "error") {
        setErrorMessage(resolution.error)
        return
      }

      router.replace(resolution.href, { scroll: false })
    }

    void bootstrap()

    return () => {
      cancelled = true
    }
  }, [queryString, router])

  if (errorMessage) {
    return (
      <ConversionEntryErrorState
        description={errorMessage}
        returnHref={returnHref}
      />
    )
  }

  return <ConversionAuthoringWorkspaceFallback />
}

function ConversionCreateRoute() {
  return (
    <React.Suspense fallback={<ConversionAuthoringWorkspaceFallback />}>
      <ConversionAuthoringWorkspace mode="create" />
    </React.Suspense>
  )
}

function ConversionUseRoute() {
  return (
    <React.Suspense fallback={<ConversionAuthoringWorkspaceFallback />}>
      <ConversionAuthoringWorkspace mode="use" />
    </React.Suspense>
  )
}

export function DesktopRoutes() {
  return (
    <Routes>
      <Route element={<HomeRedirectRoute />} path="/" />
      <Route element={<DashboardRoute />} path="/dashboard" />
      <Route element={<InventoryRoute />} path="/inventory" />
      <Route element={<AssetDetailRoute />} path="/assets/:assetId" />
      <Route element={<JobsRoute />} path="/jobs" />
      <Route element={<JobDetailRoute />} path="/jobs/:jobId" />
      <Route element={<OutputsRoute />} path="/outputs" />
      <Route element={<OutputDetailRoute />} path="/outputs/:outputId" />
      <Route element={<ReplayRoute />} path="/replay" />
      <Route element={<VisualizeRedirectRoute />} path="/visualize" />
      <Route element={<ConversionBootstrapRoute />} path="/convert" />
      <Route element={<ConversionCreateRoute />} path="/convert/new" />
      <Route element={<ConversionUseRoute />} path="/convert/use" />
      <Route element={<Navigate replace to="/dashboard" />} path="*" />
    </Routes>
  )
}
