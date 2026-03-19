import type {
  AssetSummary,
  ConversionStatus,
  ConversionSummary,
  IndexingStatus,
  JobStatus,
  JobSummary,
  JobType,
  OutputAvailability,
  OutputDetail,
  OutputFormat,
} from "@/lib/api"

const DAY_MS = 24 * 60 * 60 * 1000

const INDEXING_STATUS_ORDER: IndexingStatus[] = [
  "pending",
  "indexing",
  "indexed",
  "failed",
]

const WORKFLOW_STATUS_ORDER: JobStatus[] = [
  "queued",
  "running",
  "succeeded",
  "failed",
]

export interface TrendBucket {
  count: number
  key: string
  label: string
}

export interface CountEntry<T extends string> {
  count: number
  key: T
}

export interface AssetDashboardSummary {
  assetCount: number
  indexingStatusCounts: Record<IndexingStatus, number>
  registeredLast7d: number
  registeredLast30d: number
  registrationsByDay: TrendBucket[]
  totalAssetBytes: number
}

export interface JobDashboardSummary {
  activeCount: number
  failedLast24h: number
  statusCounts: Record<JobStatus, number>
}

export interface ConversionDashboardSummary {
  statusCounts: Record<ConversionStatus, number>
}

export interface OutputDashboardSummary {
  availabilityCounts: CountEntry<OutputAvailability>[]
  formatCounts: CountEntry<OutputFormat>[]
  outputCount: number
  outputsByDay: TrendBucket[]
  outputsCreatedLast7d: number
  totalOutputBytes: number
}

export interface RecentFailureItem {
  errorMessage: string | null
  id: string
  jobId: string
  jobType: JobType | null
  kind: "conversion" | "job"
  occurredAt: string | null
  outputFormat: string | null
}

function parseDate(value: string | null | undefined) {
  if (!value) {
    return null
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }

  return parsed
}

function isWithinWindow(
  value: string | null | undefined,
  {
    now,
    windowMs,
  }: {
    now: Date
    windowMs: number
  }
) {
  const parsed = parseDate(value)
  if (!parsed) {
    return false
  }

  const timestamp = parsed.getTime()
  return timestamp >= now.getTime() - windowMs && timestamp <= now.getTime()
}

function startOfDay(date: Date) {
  const nextDate = new Date(date)
  nextDate.setHours(0, 0, 0, 0)
  return nextDate
}

function formatDayKey(date: Date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-")
}

function formatDayLabel(date: Date) {
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
  }).format(date)
}

function createStatusCountRecord<T extends string>(keys: readonly T[]) {
  return Object.fromEntries(keys.map((key) => [key, 0])) as Record<T, number>
}

function countStatuses<T extends string>(
  values: T[],
  keys: readonly T[]
): Record<T, number> {
  const counts = createStatusCountRecord(keys)

  for (const value of values) {
    if (value in counts) {
      counts[value] += 1
    }
  }

  return counts
}

function buildCountEntries<T extends string>(
  values: T[],
  preferredOrder: readonly T[] = []
) {
  const counts = new Map<T, number>()

  for (const value of values) {
    counts.set(value, (counts.get(value) ?? 0) + 1)
  }

  const orderedKeys = [
    ...preferredOrder.filter((key) => counts.has(key)),
    ...Array.from(counts.keys())
      .filter((key) => !preferredOrder.includes(key))
      .sort((left, right) => left.localeCompare(right)),
  ]

  return orderedKeys
    .map((key) => ({
      count: counts.get(key) ?? 0,
      key,
    }))
    .sort((left, right) => {
      if (right.count !== left.count) {
        return right.count - left.count
      }

      return left.key.localeCompare(right.key)
    })
}

export function buildDailyTrend(
  values: Array<string | null | undefined>,
  days = 7,
  now = new Date()
) {
  const end = startOfDay(now)
  const countsByKey = new Map<string, number>()
  const buckets: TrendBucket[] = []

  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const day = new Date(end)
    day.setDate(end.getDate() - offset)
    const key = formatDayKey(day)
    countsByKey.set(key, 0)
    buckets.push({
      count: 0,
      key,
      label: formatDayLabel(day),
    })
  }

  for (const value of values) {
    const parsed = parseDate(value)
    if (!parsed) {
      continue
    }

    const key = formatDayKey(parsed)
    if (!countsByKey.has(key)) {
      continue
    }

    countsByKey.set(key, (countsByKey.get(key) ?? 0) + 1)
  }

  return buckets.map((bucket) => ({
    ...bucket,
    count: countsByKey.get(bucket.key) ?? 0,
  }))
}

function getJobFailureTimestamp(job: JobSummary) {
  return job.finished_at ?? job.updated_at ?? job.created_at
}

function getConversionFailureTimestamp(conversion: ConversionSummary) {
  return conversion.updated_at ?? conversion.created_at
}

function getConversionOutputFormat(conversion: ConversionSummary) {
  const output = conversion.config.output
  if (!output || typeof output !== "object" || Array.isArray(output)) {
    return null
  }

  const format = (output as Record<string, unknown>).format
  return typeof format === "string" && format.trim() ? format.trim() : null
}

export function summarizeAssets(
  assets: AssetSummary[],
  now = new Date()
): AssetDashboardSummary {
  return {
    assetCount: assets.length,
    indexingStatusCounts: countStatuses(
      assets.map((asset) => asset.indexing_status),
      INDEXING_STATUS_ORDER
    ),
    registeredLast7d: assets.filter((asset) =>
      isWithinWindow(asset.registered_time, { now, windowMs: DAY_MS * 7 })
    ).length,
    registeredLast30d: assets.filter((asset) =>
      isWithinWindow(asset.registered_time, { now, windowMs: DAY_MS * 30 })
    ).length,
    registrationsByDay: buildDailyTrend(
      assets.map((asset) => asset.registered_time),
      7,
      now
    ),
    totalAssetBytes: assets.reduce(
      (total, asset) => total + asset.file_size,
      0
    ),
  }
}

export function summarizeJobs(
  jobs: JobSummary[],
  now = new Date()
): JobDashboardSummary {
  const statusCounts = countStatuses(
    jobs.map((job) => job.status),
    WORKFLOW_STATUS_ORDER
  )

  return {
    activeCount: statusCounts.queued + statusCounts.running,
    failedLast24h: jobs.filter(
      (job) =>
        job.status === "failed" &&
        isWithinWindow(getJobFailureTimestamp(job), {
          now,
          windowMs: DAY_MS,
        })
    ).length,
    statusCounts,
  }
}

export function summarizeConversions(conversions: ConversionSummary[]) {
  return {
    statusCounts: countStatuses(
      conversions.map((conversion) => conversion.status),
      WORKFLOW_STATUS_ORDER
    ),
  }
}

export function summarizeOutputs(
  outputs: OutputDetail[],
  now = new Date()
): OutputDashboardSummary {
  return {
    availabilityCounts: buildCountEntries(
      outputs.map((output) => output.availability_status)
    ),
    formatCounts: buildCountEntries(outputs.map((output) => output.format)),
    outputCount: outputs.length,
    outputsByDay: buildDailyTrend(
      outputs.map((output) => output.created_at),
      7,
      now
    ),
    outputsCreatedLast7d: outputs.filter((output) =>
      isWithinWindow(output.created_at, {
        now,
        windowMs: DAY_MS * 7,
      })
    ).length,
    totalOutputBytes: outputs.reduce(
      (total, output) => total + output.size_bytes,
      0
    ),
  }
}

export function buildRecentFailures(
  jobs: JobSummary[],
  conversions: ConversionSummary[],
  limit = 8
) {
  const failedConversionJobIds = new Set(
    conversions
      .filter((conversion) => conversion.status === "failed")
      .map((conversion) => conversion.job_id)
  )

  const failures: Array<RecentFailureItem & { sortTimestamp: number }> = [
    ...jobs
      .filter(
        (job) =>
          job.status === "failed" &&
          !(job.type === "convert" && failedConversionJobIds.has(job.id))
      )
      .map((job) => {
        const occurredAt = getJobFailureTimestamp(job)
        return {
          errorMessage: job.error_message,
          id: job.id,
          jobId: job.id,
          jobType: job.type,
          kind: "job" as const,
          occurredAt,
          outputFormat: null,
          sortTimestamp: parseDate(occurredAt)?.getTime() ?? 0,
        }
      }),
    ...conversions
      .filter((conversion) => conversion.status === "failed")
      .map((conversion) => {
        const occurredAt = getConversionFailureTimestamp(conversion)
        return {
          errorMessage: conversion.error_message,
          id: conversion.id,
          jobId: conversion.job_id,
          jobType: null,
          kind: "conversion" as const,
          occurredAt,
          outputFormat: getConversionOutputFormat(conversion),
          sortTimestamp: parseDate(occurredAt)?.getTime() ?? 0,
        }
      }),
  ]

  return failures
    .sort((left, right) => right.sortTimestamp - left.sortTimestamp)
    .slice(0, limit)
    .map((failure) => ({
      errorMessage: failure.errorMessage,
      id: failure.id,
      jobId: failure.jobId,
      jobType: failure.jobType,
      kind: failure.kind,
      occurredAt: failure.occurredAt,
      outputFormat: failure.outputFormat,
    }))
}

export function buildFailureTrend(
  failures: RecentFailureItem[],
  days = 7,
  now = new Date()
) {
  return buildDailyTrend(
    failures.map((failure) => failure.occurredAt),
    days,
    now
  )
}
