import type { DashboardTrendBucketResponse } from "@/lib/api"

export interface TrendBucket {
  count: number
  key: string
  label: string
}

function parseDashboardDate(value: string) {
  const parts = value.split("-").map((part) => Number(part))
  if (parts.length !== 3 || parts.some((part) => !Number.isInteger(part))) {
    return null
  }

  const [year, month, day] = parts
  return new Date(Date.UTC(year, month - 1, day))
}

function formatDashboardDayLabel(value: string) {
  const parsed = parseDashboardDate(value)
  if (!parsed) {
    return value
  }

  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(parsed)
}

export function shapeDashboardTrendBuckets(
  buckets: DashboardTrendBucketResponse[]
) {
  return buckets.map((bucket) => ({
    count: bucket.count,
    key: bucket.date,
    label: formatDashboardDayLabel(bucket.date),
  }))
}
