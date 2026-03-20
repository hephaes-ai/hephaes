import type {
  ConversionStatus,
  IndexingStatus,
  JobStatus,
  JobType,
  OutputActionType,
  OutputActionStatus,
  OutputAvailability,
  OutputFormat,
  OutputRole,
} from "@/lib/api";

export function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

export function formatDateTime(value: string | null | undefined, fallback = "Not available") {
  if (!value) {
    return fallback;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatIndexingStatus(status: IndexingStatus) {
  return `${status.slice(0, 1).toUpperCase()}${status.slice(1)}`;
}

export function formatDuration(seconds: number | null | undefined, fallback = "Not available") {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) {
    return fallback;
  }

  if (seconds < 60) {
    return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} s`;
  }

  const totalSeconds = Math.round(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const remainingSeconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${remainingSeconds}s`;
  }

  return `${minutes}m ${remainingSeconds}s`;
}

export function getIndexActionLabel(status: IndexingStatus, isRunning = false) {
  if (isRunning || status === "indexing") {
    return "Indexing...";
  }

  if (status === "failed") {
    return "Retry";
  }

  if (status === "indexed") {
    return "Reindex";
  }

  return "Index";
}

export function formatSentenceCase(value: string) {
  return `${value.slice(0, 1).toUpperCase()}${value.slice(1).replace(/_/g, " ")}`;
}

export function formatJobType(jobType: JobType) {
  return formatSentenceCase(jobType);
}

export function formatOutputFormat(format: OutputFormat) {
  if (format === "tfrecord") {
    return "TFRecord";
  }

  if (format === "jsonl") {
    return "JSONL";
  }

  if (format === "json") {
    return "JSON";
  }

  if (format === "parquet") {
    return "Parquet";
  }

  return "Unknown";
}

export function formatOutputAvailability(availability: OutputAvailability) {
  if (availability === "ready") {
    return "Ready";
  }

  if (availability === "missing") {
    return "Missing";
  }

  if (availability === "invalid") {
    return "Invalid";
  }

  return formatSentenceCase(availability);
}

export function formatOutputActionType(actionType: OutputActionType) {
  if (actionType === "refresh_metadata") {
    return "Refresh metadata";
  }

  if (actionType === "vlm_tagging") {
    return "VLM tagging";
  }

  return formatSentenceCase(actionType);
}

export function formatWorkflowStatus(status: JobStatus | ConversionStatus | OutputActionStatus) {
  return formatSentenceCase(status);
}

export function isWorkflowActiveStatus(status: JobStatus | ConversionStatus | OutputActionStatus) {
  return status === "queued" || status === "running";
}

export function getWorkflowStatusClasses(status: JobStatus | ConversionStatus | OutputActionStatus) {
  if (status === "succeeded") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200";
  }

  if (status === "running") {
    return "border-sky-500/30 bg-sky-500/10 text-sky-900 dark:text-sky-200";
  }

  if (status === "queued") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200";
  }

  if (status === "failed") {
    return "border-destructive/30 bg-destructive/10 text-destructive";
  }

  return "";
}

export function formatCount(count: number, noun: string) {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

export function formatNumber(value: number) {
  return new Intl.NumberFormat().format(value);
}

export function formatOutputRole(role: OutputRole) {
  if (role === "dataset") {
    return "Dataset";
  }

  if (role === "manifest") {
    return "Manifest";
  }

  if (role === "sidecar") {
    return "Sidecar";
  }

  return formatSentenceCase(role);
}
