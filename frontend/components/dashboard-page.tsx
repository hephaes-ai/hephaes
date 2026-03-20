"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Activity,
  ArrowRight,
  Boxes,
  Database,
  HardDrive,
  PackageOpen,
  RefreshCw,
  ServerCrash,
  ShieldAlert,
  TimerReset,
  Workflow,
} from "lucide-react"

import { AssetStatusBadge } from "@/components/asset-status-badge"
import { EmptyState } from "@/components/empty-state"
import { WorkflowStatusBadge } from "@/components/workflow-status-badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  useAssets,
  useConversions,
  useJobs,
  useOutputs,
} from "@/hooks/use-backend"
import type {
  ConversionStatus,
  IndexingStatus,
  JobStatus,
  OutputAvailability,
  OutputFormat,
} from "@/lib/api"
import { getErrorMessage } from "@/lib/api"
import {
  buildFailureTrend,
  buildRecentFailures,
  summarizeAssets,
  summarizeConversions,
  summarizeJobs,
  summarizeOutputs,
  type CountEntry,
  type RecentFailureItem,
  type TrendBucket,
} from "@/lib/dashboard"
import {
  formatDateTime,
  formatFileSize,
  formatJobType,
  formatNumber,
  formatOutputAvailability,
  formatOutputFormat,
} from "@/lib/format"
import { buildHref, buildJobDetailHref } from "@/lib/navigation"
import { buildOutputsHref } from "@/lib/outputs"
import { cn } from "@/lib/utils"

function buildJobListHref(params?: Record<string, string | null | undefined>) {
  return buildHref("/jobs", params)
}

function buildInventoryHref(
  params?: Record<string, string | null | undefined>
) {
  return buildHref("/", params)
}

function getConversionStatusHref(status: ConversionStatus) {
  return buildJobListHref({
    status,
    type: "convert",
  })
}

function getFailureTitle(failure: RecentFailureItem) {
  if (failure.kind === "job" && failure.jobType) {
    return `${formatJobType(failure.jobType)} job`
  }

  if (failure.outputFormat) {
    return `${formatOutputFormat(failure.outputFormat as OutputFormat)} conversion`
  }

  return "Conversion"
}

function DashboardPageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-5 w-80 max-w-full" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <Skeleton key={index} className="h-40 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-72 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-[360px] rounded-xl" />
    </div>
  )
}

export function DashboardPageFallback() {
  return <DashboardPageSkeleton />
}


function MetricCard({
  actionHref,
  actionLabel,
  description,
  icon: Icon,
  loading = false,
  title,
  value,
}: {
  actionHref?: string
  actionLabel?: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  loading?: boolean
  title: string
  value: string
}) {
  return (
    <Card size="sm">
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <div className="space-y-1">
          <CardDescription>{title}</CardDescription>
          {loading ? (
            <Skeleton className="h-8 w-24" />
          ) : (
            <CardTitle className="text-2xl font-semibold tracking-tight">
              {value}
            </CardTitle>
          )}
        </div>
        <div className="rounded-lg border bg-muted/60 p-2 text-muted-foreground">
          <Icon className="size-4" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <Skeleton className="h-4 w-full" />
        ) : (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
        {actionHref && actionLabel ? (
          <Button asChild size="xs" variant="outline">
            <Link href={actionHref}>
              {actionLabel}
              <ArrowRight className="size-3" />
            </Link>
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}

function CountRow({
  badge,
  count,
  href,
}: {
  badge: React.ReactNode
  count: number
  href?: string
}) {
  const content = (
    <div className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
      <div className="min-w-0">{badge}</div>
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-foreground">
          {formatNumber(count)}
        </span>
        {href ? (
          <ArrowRight className="size-3.5 text-muted-foreground" />
        ) : null}
      </div>
    </div>
  )

  if (!href) {
    return content
  }

  return (
    <Link className="block transition-colors hover:text-foreground" href={href}>
      {content}
    </Link>
  )
}

function CountCard({
  description,
  emptyLabel,
  loading = false,
  rows,
  title,
}: {
  description: string
  emptyLabel: string
  loading?: boolean
  rows: React.ReactNode[]
  title: string
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-12 rounded-lg" />
            ))}
          </div>
        ) : rows.length > 0 ? (
          <div className="space-y-2">{rows}</div>
        ) : (
          <p className="text-sm text-muted-foreground">{emptyLabel}</p>
        )}
      </CardContent>
    </Card>
  )
}

function TrendCard({
  accentClassName,
  buckets,
  description,
  loading = false,
  title,
}: {
  accentClassName: string
  buckets: TrendBucket[]
  description: string
  loading?: boolean
  title: string
}) {
  const maxValue = Math.max(...buckets.map((bucket) => bucket.count), 1)

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 7 }).map((_, index) => (
              <Skeleton key={index} className="h-5 w-full rounded-full" />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {buckets.map((bucket) => (
              <div key={bucket.key} className="flex items-center gap-3">
                <span className="w-16 shrink-0 text-xs text-muted-foreground">
                  {bucket.label}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-[width]",
                      accentClassName
                    )}
                    style={{
                      width: `${bucket.count === 0 ? 0 : Math.max((bucket.count / maxValue) * 100, 8)}%`,
                    }}
                  />
                </div>
                <span className="w-8 shrink-0 text-right text-sm font-medium">
                  {bucket.count}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function OutputCountRow({
  count,
  href,
  label,
}: {
  count: number
  href: string
  label: string
}) {
  return (
    <CountRow
      badge={<Badge variant="outline">{label}</Badge>}
      count={count}
      href={href}
    />
  )
}

export function DashboardPage() {
  const pathname = usePathname() || "/dashboard"
  const assetsResponse = useAssets()
  const jobsResponse = useJobs()
  const conversionsResponse = useConversions()
  const outputsResponse = useOutputs()

  const now = new Date()
  const currentHref = pathname

  const assetSummary = assetsResponse.data
    ? summarizeAssets(assetsResponse.data, now)
    : null
  const jobSummary = jobsResponse.data
    ? summarizeJobs(jobsResponse.data, now)
    : null
  const conversionSummary = conversionsResponse.data
    ? summarizeConversions(conversionsResponse.data)
    : null
  const outputSummary = outputsResponse.data
    ? summarizeOutputs(outputsResponse.data, now)
    : null

  const recentFailuresReady =
    (jobsResponse.data !== undefined || !!jobsResponse.error) &&
    (conversionsResponse.data !== undefined || !!conversionsResponse.error)

  const recentFailures = React.useMemo(
    () =>
      recentFailuresReady
        ? buildRecentFailures(
            jobsResponse.data ?? [],
            conversionsResponse.data ?? []
          )
        : [],
    [conversionsResponse.data, jobsResponse.data, recentFailuresReady]
  )
  const failureTrend = recentFailuresReady
    ? buildFailureTrend(recentFailures, 7, now)
    : []

  const resources = [
    {
      error: assetsResponse.error,
      isLoading: assetsResponse.isLoading,
      label: "assets",
    },
    {
      error: jobsResponse.error,
      isLoading: jobsResponse.isLoading,
      label: "jobs",
    },
    {
      error: conversionsResponse.error,
      isLoading: conversionsResponse.isLoading,
      label: "conversions",
    },
    {
      error: outputsResponse.error,
      isLoading: outputsResponse.isLoading,
      label: "outputs",
    },
  ]

  const errorMessages = resources
    .filter((resource) => resource.error)
    .map((resource) => `${resource.label}: ${getErrorMessage(resource.error)}`)

  const allLoading = resources.every((resource) => resource.isLoading)
  const allErrored = resources.every((resource) => resource.error)
  const shouldPoll =
    (jobsResponse.data ?? []).some(
      (job) => job.status === "queued" || job.status === "running"
    ) ||
    (conversionsResponse.data ?? []).some(
      (conversion) =>
        conversion.status === "queued" || conversion.status === "running"
    )

  const refreshAll = React.useCallback(async () => {
    await Promise.all([
      assetsResponse.mutate(),
      jobsResponse.mutate(),
      conversionsResponse.mutate(),
      outputsResponse.mutate(),
    ])
  }, [assetsResponse, conversionsResponse, jobsResponse, outputsResponse])

  React.useEffect(() => {
    if (!shouldPoll) {
      return
    }

    const intervalId = window.setInterval(() => {
      void refreshAll()
    }, 2000)

    return () => window.clearInterval(intervalId)
  }, [refreshAll, shouldPoll])

  const hasAnyData =
    (assetsResponse.data?.length ?? 0) > 0 ||
    (jobsResponse.data?.length ?? 0) > 0 ||
    (conversionsResponse.data?.length ?? 0) > 0 ||
    (outputsResponse.data?.length ?? 0) > 0

  const isFullyLoadedWithoutData =
    !allLoading &&
    !allErrored &&
    resources.every((resource) => !resource.isLoading && !resource.error) &&
    !hasAnyData

  if (allLoading) {
    return <DashboardPageSkeleton />
  }

  if (allErrored) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertTitle>Dashboard unavailable</AlertTitle>
          <AlertDescription>{errorMessages.join(" ")}</AlertDescription>
        </Alert>
        <div>
          <Button
            onClick={() => void refreshAll()}
            type="button"
            variant="outline"
          >
            Try again
          </Button>
        </div>
      </div>
    )
  }

  if (isFullyLoadedWithoutData) {
    return (
      <EmptyState
        action={
          <Button asChild size="sm" variant="outline">
            <Link href="/">Open inventory</Link>
          </Button>
        }
        description="Register assets, run indexing, and create outputs to populate the operational dashboard."
        title="No dashboard data yet"
      />
    )
  }

  const assetRows: React.ReactNode[] = assetSummary
    ? (
        [
          ["pending", buildInventoryHref({ status: "pending" })],
          ["indexing", buildInventoryHref({ status: "indexing" })],
          ["indexed", buildInventoryHref({ status: "indexed" })],
          ["failed", buildInventoryHref({ status: "failed" })],
        ] as Array<[IndexingStatus, string]>
      ).map(([status, href]) => (
        <CountRow
          badge={<AssetStatusBadge status={status} />}
          count={assetSummary.indexingStatusCounts[status]}
          href={href}
          key={status}
        />
      ))
    : []

  const jobRows: React.ReactNode[] = jobSummary
    ? (
        [
          ["queued", buildJobListHref({ status: "queued" })],
          ["running", buildJobListHref({ status: "running" })],
          ["succeeded", buildJobListHref({ status: "succeeded" })],
          ["failed", buildJobListHref({ status: "failed" })],
        ] as Array<[JobStatus, string]>
      ).map(([status, href]) => (
        <CountRow
          badge={<WorkflowStatusBadge status={status} />}
          count={jobSummary.statusCounts[status]}
          href={href}
          key={status}
        />
      ))
    : []

  const conversionRows: React.ReactNode[] = conversionSummary
    ? (["queued", "running", "succeeded", "failed"] as ConversionStatus[]).map(
        (status) => (
          <CountRow
            badge={<WorkflowStatusBadge status={status} />}
            count={conversionSummary.statusCounts[status]}
            href={getConversionStatusHref(status)}
            key={status}
          />
        )
      )
    : []

  const outputAvailabilityRows: React.ReactNode[] = outputSummary
    ? outputSummary.availabilityCounts.map(
        (entry: CountEntry<OutputAvailability>) => (
          <OutputCountRow
            count={entry.count}
            href={buildOutputsHref({ availability: entry.key })}
            key={entry.key}
            label={formatOutputAvailability(entry.key)}
          />
        )
      )
    : []

  const outputFormatRows: React.ReactNode[] = outputSummary
    ? outputSummary.formatCounts.map((entry: CountEntry<OutputFormat>) => (
        <OutputCountRow
          count={entry.count}
          href={buildOutputsHref({ format: entry.key })}
          key={entry.key}
          label={formatOutputFormat(entry.key)}
        />
      ))
    : []

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">
                Dashboard
              </h1>
              {hasAnyData ? (
                <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                  Phase 1 client aggregation
                </span>
              ) : null}
            </div>
            <p className="max-w-3xl text-sm text-muted-foreground">
              Operational overview built from the existing asset, job,
              conversion, and output routes.
            </p>
          </div>
          <Button
            disabled={allLoading}
            onClick={() => void refreshAll()}
            size="sm"
            type="button"
            variant="outline"
          >
            <RefreshCw className="size-4" />
            Refresh
          </Button>
        </div>
      </section>

      {errorMessages.length > 0 ? (
        <Alert className="border-amber-500/30 bg-amber-500/10 text-amber-950 dark:text-amber-100">
          <AlertTitle>Showing partial dashboard data</AlertTitle>
          <AlertDescription>{errorMessages.join(" ")}</AlertDescription>
        </Alert>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          actionHref="/"
          actionLabel="Open inventory"
          description={
            assetSummary
              ? `${formatNumber(assetSummary.registeredLast30d)} added in the last 30 days`
              : "Loading asset totals"
          }
          icon={Boxes}
          loading={!assetSummary}
          title="Total assets"
          value={assetSummary ? formatNumber(assetSummary.assetCount) : "0"}
        />
        <MetricCard
          actionHref="/"
          actionLabel="Inspect storage"
          description={
            assetSummary
              ? `${formatNumber(assetSummary.registeredLast7d)} registered in the last 7 days`
              : "Loading asset storage"
          }
          icon={HardDrive}
          loading={!assetSummary}
          title="Total storage"
          value={
            assetSummary ? formatFileSize(assetSummary.totalAssetBytes) : "0 B"
          }
        />
        <MetricCard
          actionHref="/jobs"
          actionLabel="Open jobs"
          description={
            jobSummary
              ? `${formatNumber(jobSummary.failedLast24h)} failures in the last 24 hours`
              : "Loading workflow activity"
          }
          icon={Activity}
          loading={!jobSummary}
          title="Active jobs"
          value={jobSummary ? formatNumber(jobSummary.activeCount) : "0"}
        />
        <MetricCard
          actionHref="/outputs"
          actionLabel="Open outputs"
          description={
            outputSummary
              ? `${formatNumber(outputSummary.outputsCreatedLast7d)} created in the last 7 days`
              : "Loading output catalog"
          }
          icon={Database}
          loading={!outputSummary}
          title="Output artifacts"
          value={outputSummary ? formatNumber(outputSummary.outputCount) : "0"}
        />
        <MetricCard
          actionHref={buildInventoryHref({
            start_after: new Date(
              now.getTime() - 7 * 24 * 60 * 60 * 1000
            ).toISOString(),
          })}
          actionLabel="View recent assets"
          description="Assets registered during the last 7 days."
          icon={TimerReset}
          loading={!assetSummary}
          title="New assets (7d)"
          value={
            assetSummary ? formatNumber(assetSummary.registeredLast7d) : "0"
          }
        />
        <MetricCard
          actionHref={buildJobListHref({ status: "failed" })}
          actionLabel="Open failures"
          description="Failed jobs observed during the last 24 hours."
          icon={ServerCrash}
          loading={!jobSummary}
          title="Failed jobs (24h)"
          value={jobSummary ? formatNumber(jobSummary.failedLast24h) : "0"}
        />
        <MetricCard
          actionHref="/outputs"
          actionLabel="Inspect bytes"
          description="Total bytes reported by current output artifacts."
          icon={PackageOpen}
          loading={!outputSummary}
          title="Output bytes"
          value={
            outputSummary
              ? formatFileSize(outputSummary.totalOutputBytes)
              : "0 B"
          }
        />
        <MetricCard
          actionHref={buildJobListHref({ type: "convert" })}
          actionLabel="Open conversion jobs"
          description="Succeeded, running, queued, and failed conversion work."
          icon={Workflow}
          loading={!conversionSummary}
          title="Conversions tracked"
          value={
            conversionSummary
              ? formatNumber(
                  Object.values(conversionSummary.statusCounts).reduce(
                    (total, count) => total + count,
                    0
                  )
                )
              : "0"
          }
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <CountCard
          description="Inventory readiness based on current asset indexing state."
          emptyLabel="No asset status data yet."
          loading={!assetSummary}
          rows={assetRows}
          title="Indexing status"
        />
        <CountCard
          description="Current durable backend jobs across indexing, conversion, and visualization work."
          emptyLabel="No jobs yet."
          loading={!jobSummary}
          rows={jobRows}
          title="Job status"
        />
        <CountCard
          description="Conversion health using the existing conversions list route."
          emptyLabel="No conversions yet."
          loading={!conversionSummary}
          rows={conversionRows}
          title="Conversion status"
        />
        <CountCard
          description="Output availability from the first-class artifact catalog."
          emptyLabel="No outputs yet."
          loading={!outputSummary}
          rows={outputAvailabilityRows}
          title="Output availability"
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <TrendCard
          accentClassName="bg-sky-500/70"
          buckets={assetSummary?.registrationsByDay ?? []}
          description="Assets registered each day over the last week."
          loading={!assetSummary}
          title="Registrations (7d)"
        />
        <TrendCard
          accentClassName="bg-amber-500/70"
          buckets={failureTrend}
          description="Recent failed jobs and failed conversions by day."
          loading={!recentFailuresReady}
          title="Failures (7d)"
        />
        <TrendCard
          accentClassName="bg-emerald-500/70"
          buckets={outputSummary?.outputsByDay ?? []}
          description="Output artifacts created each day over the last week."
          loading={!outputSummary}
          title="Outputs (7d)"
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <CountCard
          description="Formats currently represented in the output catalog."
          emptyLabel="No output formats yet."
          loading={!outputSummary}
          rows={outputFormatRows}
          title="Outputs by format"
        />
        <Card>
          <CardHeader>
            <CardTitle>What is blocked</CardTitle>
            <CardDescription>
              Quick links into the highest-friction operational states.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <CountRow
              badge={<Badge variant="outline">Pending assets</Badge>}
              count={assetSummary?.indexingStatusCounts.pending ?? 0}
              href={buildInventoryHref({ status: "pending" })}
            />
            <CountRow
              badge={<Badge variant="outline">Failed assets</Badge>}
              count={assetSummary?.indexingStatusCounts.failed ?? 0}
              href={buildInventoryHref({ status: "failed" })}
            />
            <CountRow
              badge={<Badge variant="outline">Failed jobs</Badge>}
              count={jobSummary?.statusCounts.failed ?? 0}
              href={buildJobListHref({ status: "failed" })}
            />
            <CountRow
              badge={<Badge variant="outline">Missing outputs</Badge>}
              count={
                outputSummary?.availabilityCounts.find(
                  (entry) => entry.key === "missing"
                )?.count ?? 0
              }
              href={buildOutputsHref({ availability: "missing" })}
            />
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldAlert className="size-4 text-muted-foreground" />
            Recent failures
          </CardTitle>
          <CardDescription>
            Latest failed jobs and failed conversions, with direct links back
            into job detail.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!recentFailuresReady ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-12 rounded-lg" />
              ))}
            </div>
          ) : recentFailures.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No recent failures recorded.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead>Failure</TableHead>
                  <TableHead>When</TableHead>
                  <TableHead>Details</TableHead>
                  <TableHead className="w-[110px] text-right">Open</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentFailures.map((failure) => (
                  <TableRow key={`${failure.kind}:${failure.id}`}>
                    <TableCell>
                      <Badge
                        variant={
                          failure.kind === "conversion"
                            ? "outline"
                            : "secondary"
                        }
                      >
                        {failure.kind === "conversion" ? "Conversion" : "Job"}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-medium">
                      {getFailureTitle(failure)}
                    </TableCell>
                    <TableCell>{formatDateTime(failure.occurredAt)}</TableCell>
                    <TableCell className="max-w-md text-sm text-muted-foreground">
                      {failure.errorMessage ?? "No error message recorded."}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="xs" variant="outline">
                        <Link
                          href={buildJobDetailHref(failure.jobId, currentHref)}
                        >
                          Open
                          <ArrowRight className="size-3" />
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
