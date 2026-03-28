import * as React from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useParams,
} from "react-router-dom";

import DashboardRoute from "../app/dashboard/page";
import InventoryRoute from "../app/inventory/page";
import JobsRoute from "../app/jobs/page";
import OutputsRoute from "../app/outputs/page";
import ReplayRoute from "../app/replay/page";
import ConversionCreateRoute from "../app/convert/new/page";
import ConversionUseRoute from "../app/convert/use/page";
import {
  AssetDetailPage,
  AssetDetailPageFallback,
} from "../app/assets/[assetId]/asset-detail-page";
import {
  ConversionAuthoringWorkspaceFallback,
} from "../app/convert/conversion-authoring-workspace";
import {
  JobDetailPage,
  JobDetailPageFallback,
} from "../app/jobs/[jobId]/job-detail-page";
import {
  OutputDetailPage,
  OutputDetailPageFallback,
} from "../app/outputs/[outputId]/output-detail-page";

import { AppProviders } from "@/components/app-providers";
import { AppShell } from "@/components/app-shell";
import {
  useAppRouter,
  useAppSearchParams,
} from "@/lib/app-routing";
import { ConversionEntryErrorState } from "@/components/conversion-entry-state";
import { resolveConversionEntry } from "@/lib/conversion-entry";
import { resolveReturnHref } from "@/lib/navigation";

function HomeRedirectRoute() {
  const searchParams = useAppSearchParams();
  const query = searchParams.toString();

  return <Navigate replace to={query ? `/inventory?${query}` : "/dashboard"} />;
}

function VisualizeRedirectRoute() {
  const searchParams = useAppSearchParams();
  const query = searchParams.toString();

  return <Navigate replace to={query ? `/replay?${query}` : "/replay"} />;
}

function AssetDetailRoute() {
  const params = useParams<{ assetId: string }>();
  const assetId = params.assetId?.trim();

  if (!assetId) {
    return <Navigate replace to="/inventory" />;
  }

  return (
    <React.Suspense fallback={<AssetDetailPageFallback />}>
      <AssetDetailPage assetId={assetId} />
    </React.Suspense>
  );
}

function JobDetailRoute() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId?.trim();

  if (!jobId) {
    return <Navigate replace to="/jobs" />;
  }

  return (
    <React.Suspense fallback={<JobDetailPageFallback />}>
      <JobDetailPage jobId={jobId} />
    </React.Suspense>
  );
}

function OutputDetailRoute() {
  const params = useParams<{ outputId: string }>();
  const outputId = params.outputId?.trim();

  if (!outputId) {
    return <Navigate replace to="/outputs" />;
  }

  return (
    <React.Suspense fallback={<OutputDetailPageFallback />}>
      <OutputDetailPage outputId={outputId} />
    </React.Suspense>
  );
}

function ConversionBootstrapRoute() {
  const router = useAppRouter();
  const searchParams = useAppSearchParams();
  const queryString = searchParams.toString();
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const returnHref = resolveReturnHref(searchParams.get("from"), "/inventory");

  React.useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setErrorMessage(null);
      const resolution = await resolveConversionEntry(
        new URLSearchParams(queryString)
      );

      if (cancelled) {
        return;
      }

      if (resolution.status === "error") {
        setErrorMessage(resolution.error);
        return;
      }

      router.replace(resolution.href, { scroll: false });
    }

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, [queryString, router]);

  if (errorMessage) {
    return (
      <ConversionEntryErrorState
        description={errorMessage}
        returnHref={returnHref}
      />
    );
  }

  return <ConversionAuthoringWorkspaceFallback />;
}

function DesktopRoutes() {
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
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppProviders>
        <AppShell>
          <DesktopRoutes />
        </AppShell>
      </AppProviders>
    </BrowserRouter>
  );
}
