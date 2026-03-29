"use client"

import * as React from "react"
import {
  Activity,
  ArrowRight,
  Boxes,
  Database,
  HardDrive,
  PackageOpen,
  RefreshCw,
  ServerCrash,
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
  useDashboardBlockers,
  useDashboardSummary,
  useDashboardTrends,
} from "@/hooks/use-backend"
import type {
  IndexingStatus,
  JobStatus,
} from "@/lib/api"
import { getErrorMessage } from "@/lib/api"
import { AppLink as Link } from "@/lib/app-routing"
import { shapeDashboardTrendBuckets, type TrendBucket } from "@/lib/dashboard"
import {
  formatDateTime,
  formatFileSize,
  formatNumber,
} from "@/lib/format"
import { buildHref } from "@/lib/navigation"
import { buildOutputsHref } from "@/lib/outputs"
import { cn } from "@/lib/utils"

const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? React.useLayoutEffect : React.useEffect

function buildJobListHref(params?: Record<string, string | null | undefined>) {
  return buildHref("/jobs", params)
}

function buildInventoryHref(
  params?: Record<string, string | null | undefined>
) {
  return buildHref("/inventory", params)
}

function getConversionStatusHref(status: string) {
  return buildJobListHref({
    status,
    type: "convert",
  })
}

function DashboardPageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-5 w-80 max-w-full" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, index) => (
          <Skeleton key={index} className="h-[360px] rounded-xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, index) => (
          <Skeleton key={index} className="h-[320px] rounded-xl" />
        ))}
      </div>
    </div>
  )
}

export function DashboardPageFallback() {
  return <DashboardPageSkeleton />
}


function MetricTile({
  actionHref,
  actionLabel,
  icon: Icon,
  loading = false,
  title,
  value,
}: {
  actionHref?: string
  actionLabel?: string
  icon: React.ComponentType<{ className?: string }>
  loading?: boolean
  title: string
  value: string
}) {
  const metricChip = loading ? (
    <div className="flex shrink-0 items-center gap-2 rounded-lg border bg-muted/60 px-3 py-2 text-muted-foreground">
      <Icon className="size-4 shrink-0" />
      <Skeleton className="h-4 w-12" />
    </div>
  ) : actionHref ? (
    <Link
      aria-label={`${actionLabel ?? title}: ${value}`}
      className="flex shrink-0 items-center gap-2 rounded-lg border bg-muted/60 px-3 py-2 text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      href={actionHref}
    >
      <Icon className="size-4 shrink-0" />
      <span className="whitespace-nowrap text-sm font-semibold leading-none text-foreground tabular-nums">
        {value}
      </span>
    </Link>
  ) : (
    <div className="flex shrink-0 items-center gap-2 rounded-lg border bg-muted/60 px-3 py-2 text-muted-foreground">
      <Icon className="size-4 shrink-0" />
      <span className="whitespace-nowrap text-sm font-semibold leading-none text-foreground tabular-nums">
        {value}
      </span>
    </div>
  )

  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-muted/20 px-4 py-3 transition-colors hover:bg-muted/30">
      <div className="min-w-0">
        <div className="text-sm font-medium tracking-tight text-foreground">
          {title}
        </div>
      </div>
      {metricChip}
    </div>
  )
}

type MetricTileConfig = {
  actionHref?: string
  actionLabel?: string
  icon: React.ComponentType<{ className?: string }>
  key: string
  loading?: boolean
  title: string
  value: string
}

function DashboardMetricsSection({
  computedAt,
  summary,
}: {
  computedAt: Date
  summary: {
    inventory: {
      asset_count: number
      registered_last_24h: number
      registered_last_30d: number
      registered_last_7d: number
      total_asset_bytes: number
    }
    jobs: {
      active_count: number
      failed_last_24h: number
    }
    outputs: {
      output_count: number
      outputs_created_last_7d: number
      total_output_bytes: number
    }
  } | null
}) {
  const metrics: MetricTileConfig[] = [
    {
      actionHref: "/inventory",
      actionLabel: "Open inventory",
      icon: Boxes,
      key: "total-assets",
      loading: !summary,
      title: "Total assets",
      value: summary ? formatNumber(summary.inventory.asset_count) : "0",
    },
    {
      actionHref: "/inventory",
      actionLabel: "Inspect storage",
      icon: HardDrive,
      key: "total-storage",
      loading: !summary,
      title: "Total storage",
      value: summary ? formatFileSize(summary.inventory.total_asset_bytes) : "0 B",
    },
    {
      actionHref: "/jobs",
      actionLabel: "Open jobs",
      icon: Activity,
      key: "active-jobs",
      loading: !summary,
      title: "Active jobs",
      value: summary ? formatNumber(summary.jobs.active_count) : "0",
    },
    {
      actionHref: "/outputs",
      actionLabel: "Open outputs",
      icon: Database,
      key: "output-artifacts",
      loading: !summary,
      title: "Output artifacts",
      value: summary ? formatNumber(summary.outputs.output_count) : "0",
    },
    {
      actionHref: buildInventoryHref({
        start_after: new Date(
          computedAt.getTime() - 7 * 24 * 60 * 60 * 1000
        ).toISOString(),
      }),
      actionLabel: "View recent assets",
      icon: TimerReset,
      key: "new-assets-7d",
      loading: !summary,
      title: "New assets (7d)",
      value: summary ? formatNumber(summary.inventory.registered_last_7d) : "0",
    },
    {
      actionHref: buildJobListHref({ status: "failed" }),
      actionLabel: "Open failures",
      icon: ServerCrash,
      key: "failed-jobs-24h",
      loading: !summary,
      title: "Failed jobs (24h)",
      value: summary ? formatNumber(summary.jobs.failed_last_24h) : "0",
    },
    {
      actionHref: "/outputs",
      actionLabel: "Inspect bytes",
      icon: PackageOpen,
      key: "output-bytes",
      loading: !summary,
      title: "Output bytes",
      value: summary ? formatFileSize(summary.outputs.total_output_bytes) : "0 B",
    },
    {
      actionHref: buildInventoryHref({
        start_after: new Date(
          computedAt.getTime() - 24 * 60 * 60 * 1000
        ).toISOString(),
      }),
      actionLabel: "View recent assets",
      icon: Workflow,
      key: "new-assets-24h",
      loading: !summary,
      title: "New assets (24h)",
      value: summary ? formatNumber(summary.inventory.registered_last_24h) : "0",
    },
  ]

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {metrics.map((metric) => (
        <MetricTile
          actionHref={metric.actionHref}
          actionLabel={metric.actionLabel}
          icon={metric.icon}
          key={metric.key}
          loading={metric.loading}
          title={metric.title}
          value={metric.value}
        />
      ))}
    </div>
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

type StatusTab = {
  emptyLabel: string
  key: string
  label: string
  rows: React.ReactNode[]
}

function StatusTabsCard({
  tabs,
  title,
}: {
  tabs: StatusTab[]
  title: string
}) {
  const [activeTab, setActiveTab] = React.useState(tabs[0]?.key ?? "")
  const activeTabData =
    tabs.find((tab) => tab.key === activeTab) ?? tabs[0] ?? null
  const baseId = React.useId()

  if (!activeTabData) {
    return (
      <Card>
        <CardHeader className="flex flex-col gap-3">
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No status data yet.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3">
        <CardTitle>{title}</CardTitle>
        <div aria-label={`${title} tabs`} role="tablist">
          <div className="flex flex-wrap gap-2">
            {tabs.map((tab) => {
              const isActive = tab.key === activeTabData.key

              return (
                <button
                  aria-controls={`${baseId}-panel-${tab.key}`}
                  aria-selected={isActive}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                    isActive
                      ? "border-foreground bg-foreground text-background shadow-sm"
                      : "border-border bg-background text-muted-foreground hover:text-foreground"
                  )}
                  id={`${baseId}-tab-${tab.key}`}
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  role="tab"
                  type="button"
                >
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {activeTabData.rows.length > 0 ? (
          <div
            aria-labelledby={`${baseId}-tab-${activeTabData.key}`}
            className="space-y-2"
            id={`${baseId}-panel-${activeTabData.key}`}
            role="tabpanel"
          >
            {activeTabData.rows}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {activeTabData.emptyLabel}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function TrendChart({
  accentClassName,
  animate = true,
  buckets,
  emptyLabel,
  loading = false,
}: {
  accentClassName: string
  animate?: boolean
  buckets: TrendBucket[]
  emptyLabel: string
  loading?: boolean
}) {
  const maxValue = Math.max(...buckets.map((bucket) => bucket.count), 1)

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 7 }).map((_, index) => (
          <Skeleton key={index} className="h-5 w-full rounded-full" />
        ))}
      </div>
    )
  }

  if (buckets.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyLabel}</p>
  }

  return (
    <div className="space-y-3">
      {buckets.map((bucket) => {
        const width = bucket.count === 0 ? 0 : Math.max((bucket.count / maxValue) * 100, 8)

        return (
          <div key={bucket.key} className="flex items-center gap-3">
            <span className="w-16 shrink-0 text-xs text-muted-foreground">
              {bucket.label}
            </span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full"
                style={{
                  width: `${width}%`,
                }}
              >
                <div
                  className={cn(
                    "h-full w-full origin-left rounded-full transition-transform duration-500 ease-out",
                    animate ? "scale-x-100" : "scale-x-0",
                    accentClassName
                  )}
                />
              </div>
            </div>
            <span className="w-8 shrink-0 text-right text-sm font-medium">
              {bucket.count}
            </span>
          </div>
        )
      })}
    </div>
  )
}

type TrendTab = {
  accentClassName: string
  buckets: TrendBucket[]
  emptyLabel: string
  key: string
  label: string
}

function TrendTabsCard({
  className,
  loading = false,
  tabs,
  title,
}: {
  className?: string
  loading?: boolean
  tabs: TrendTab[]
  title: string
}) {
  const [activeTab, setActiveTab] = React.useState(tabs[0]?.key ?? "")
  const activeTabData =
    tabs.find((tab) => tab.key === activeTab) ?? tabs[0] ?? null
  const activeTabKey = activeTabData?.key ?? ""
  const [animateBars, setAnimateBars] = React.useState(false)
  const baseId = React.useId()

  useIsomorphicLayoutEffect(() => {
    if (!activeTabKey) {
      return
    }

    setAnimateBars(false)
    const frame = window.requestAnimationFrame(() => setAnimateBars(true))

    return () => window.cancelAnimationFrame(frame)
  }, [activeTabKey])

  if (!activeTabData) {
    return (
      <Card>
        <CardHeader className="flex flex-col gap-3">
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No trend data yet.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader className="flex flex-col gap-3">
        <CardTitle>{title}</CardTitle>
        <div aria-label={`${title} tabs`} role="tablist">
          <div className="flex flex-wrap gap-2">
            {tabs.map((tab) => {
              const isActive = tab.key === activeTabData.key

              return (
                <button
                  aria-controls={`${baseId}-panel-${tab.key}`}
                  aria-selected={isActive}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                    isActive
                      ? "border-foreground bg-foreground text-background shadow-sm"
                      : "border-border bg-background text-muted-foreground hover:text-foreground"
                  )}
                  id={`${baseId}-tab-${tab.key}`}
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  role="tab"
                  type="button"
                >
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>
      </CardHeader>
      <CardContent className="min-h-[15rem]">
        <div
          aria-labelledby={`${baseId}-tab-${activeTabData.key}`}
          id={`${baseId}-panel-${activeTabData.key}`}
          key={activeTabData.key}
          role="tabpanel"
        >
          <TrendChart
            accentClassName={activeTabData.accentClassName}
            animate={animateBars}
            buckets={activeTabData.buckets}
            emptyLabel={activeTabData.emptyLabel}
            loading={loading}
          />
        </div>
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const blockersResponse = useDashboardBlockers()
  const summaryResponse = useDashboardSummary()
  const trendsResponse = useDashboardTrends(7)

  const blockers = blockersResponse.data ?? null
  const summary = summaryResponse.data ?? null
  const trends = trendsResponse.data ?? null
  const computedAt = summary?.freshness.computed_at
    ? new Date(summary.freshness.computed_at)
    : new Date()
  const registrationsTrend = trends
    ? shapeDashboardTrendBuckets(trends.registrations_by_day)
    : []
  const jobFailuresTrend = trends
    ? shapeDashboardTrendBuckets(trends.job_failures_by_day)
    : []
  const conversionFailuresTrend = trends
    ? shapeDashboardTrendBuckets(trends.conversion_failures_by_day)
    : []
  const outputsTrend = trends
    ? shapeDashboardTrendBuckets(trends.outputs_created_by_day)
    : []

  const resources = [
    {
      error: blockersResponse.error,
      isLoading: blockersResponse.isLoading,
      label: "blockers",
    },
    {
      error: summaryResponse.error,
      isLoading: summaryResponse.isLoading,
      label: "summary",
    },
    {
      error: trendsResponse.error,
      isLoading: trendsResponse.isLoading,
      label: "trends",
    },
  ]

  const errorMessages = resources
    .filter((resource) => resource.error)
    .map((resource) => `${resource.label}: ${getErrorMessage(resource.error)}`)

  const summaryUnavailable = !summary && !!summaryResponse.error
  const shouldPoll =
    (summary?.jobs.active_count ?? 0) > 0 ||
    (summary?.conversions.status_counts.queued ?? 0) > 0 ||
    (summary?.conversions.status_counts.running ?? 0) > 0

  const refreshAll = React.useCallback(async () => {
    await Promise.all([
      blockersResponse.mutate(),
      summaryResponse.mutate(),
      trendsResponse.mutate(),
    ])
  }, [blockersResponse, summaryResponse, trendsResponse])

  React.useEffect(() => {
    if (!shouldPoll) {
      return
    }

    const intervalId = window.setInterval(() => {
      void refreshAll()
    }, 2000)

    return () => window.clearInterval(intervalId)
  }, [refreshAll, shouldPoll])

  const hasAnyData = summary
    ? summary.inventory.asset_count > 0 ||
      summary.jobs.active_count > 0 ||
      Object.values(summary.jobs.status_counts).some((count) => count > 0) ||
      Object.values(summary.conversions.status_counts).some(
        (count) => count > 0
      ) ||
      summary.outputs.output_count > 0
    : false

  if (!summary && summaryResponse.isLoading) {
    return <DashboardPageSkeleton />
  }

  if (summaryUnavailable) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertTitle>Dashboard unavailable</AlertTitle>
          <AlertDescription>
            {getErrorMessage(summaryResponse.error)}
          </AlertDescription>
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

  if (summary && !hasAnyData) {
    return (
      <EmptyState
        action={
          <Button asChild size="sm" variant="outline">
            <Link href="/inventory">Open inventory</Link>
          </Button>
        }
        description="Register assets, run indexing, and create outputs to populate the operational dashboard."
        title="No dashboard data yet"
      />
    )
  }

  const assetRows: React.ReactNode[] = summary
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
          count={summary.indexing.status_counts[status] ?? 0}
          href={href}
          key={status}
        />
      ))
    : []

  const jobRows: React.ReactNode[] = summary
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
          count={summary.jobs.status_counts[status] ?? 0}
          href={href}
          key={status}
        />
      ))
    : []

  const conversionRows: React.ReactNode[] = summary
    ? (["queued", "running", "succeeded", "failed"] as const).map(
        (status) => (
          <CountRow
            badge={<WorkflowStatusBadge status={status} />}
            count={summary.conversions.status_counts[status] ?? 0}
            href={getConversionStatusHref(status)}
            key={status}
          />
        )
      )
    : []

  const blockerRows: React.ReactNode[] = blockers
    ? [
        {
          count: blockers.pending_assets,
          href: buildInventoryHref({ status: "pending" }),
          label: "Pending assets",
        },
        {
          count: blockers.failed_assets,
          href: buildInventoryHref({ status: "failed" }),
          label: "Failed assets",
        },
        {
          count: blockers.failed_jobs,
          href: buildJobListHref({ status: "failed" }),
          label: "Failed jobs",
        },
        {
          count: blockers.failed_conversions,
          href: getConversionStatusHref("failed"),
          label: "Failed conversions",
        },
        {
          count: blockers.missing_outputs,
          href: buildOutputsHref({ availability: "missing" }),
          label: "Missing outputs",
        },
        {
          count: blockers.invalid_outputs,
          href: buildOutputsHref({ availability: "invalid" }),
          label: "Invalid outputs",
        },
      ].map((row) => (
        <CountRow
          badge={<Badge variant="outline">{row.label}</Badge>}
          count={row.count}
          href={row.href}
          key={row.label}
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
              {summary ? (
                <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                  v0.1.0
                </span>
              ) : null}
            </div>
            {summary ? (
              <p className="text-xs text-muted-foreground">
                Last computed {formatDateTime(summary.freshness.computed_at)}
              </p>
            ) : null}
          </div>
          <Button
            disabled={!summary && summaryResponse.isLoading}
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

      <section className="grid gap-4 lg:grid-cols-2">
        <DashboardMetricsSection summary={summary} computedAt={computedAt} />
        <StatusTabsCard
          tabs={[
            {
              emptyLabel: "No asset status data yet.",
              key: "indexing",
              label: "Indexing",
              rows: assetRows,
            },
            {
              emptyLabel: "No jobs yet.",
              key: "jobs",
              label: "Jobs",
              rows: jobRows,
            },
            {
              emptyLabel: "No conversions yet.",
              key: "conversion",
              label: "Conversion",
              rows: conversionRows,
            },
          ]}
          title="Operational status"
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <TrendTabsCard
          loading={!trends && !trendsResponse.error}
          tabs={[
            {
              accentClassName: "bg-sky-500/70",
              buckets: registrationsTrend,
              emptyLabel: "Registration trend data unavailable.",
              key: "registrations",
              label: "Registrations",
            },
            {
              accentClassName: "bg-amber-500/70",
              buckets: jobFailuresTrend,
              emptyLabel: "Job failure trend data unavailable.",
              key: "job-failures",
              label: "Job failures",
            },
            {
              accentClassName: "bg-rose-500/70",
              buckets: conversionFailuresTrend,
              emptyLabel: "Conversion failure trend data unavailable.",
              key: "conversion-failures",
              label: "Conversion failures",
            },
            {
              accentClassName: "bg-emerald-500/70",
              buckets: outputsTrend,
              emptyLabel: "Output trend data unavailable.",
              key: "outputs",
              label: "Outputs",
            },
          ]}
          title="Recent Activity (7d)"
        />
        <CountCard
          description="Quick links into the highest-friction operational states."
          emptyLabel="No blocker summary yet."
          loading={!blockers && !blockersResponse.error}
          rows={blockerRows}
          title="What is blocked"
        />
      </section>
    </div>
  )
}
