import type {
  ConversionSpec,
  InspectionResult,
  SavedConversionConfigDetailResponse,
  TopicInspectionResult,
} from "@/lib/api"

export interface ConversionSpecSummary {
  featureCount: number
  labelPrimary: string | null
  outputCompression: string | null
  outputFormat: string | null
  rowStrategyKind: string | null
  schemaName: string | null
  schemaVersion: number | null
  writeManifest: boolean | null
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function getRecord(value: unknown, key: string): Record<string, unknown> | null {
  if (!isRecord(value)) {
    return null
  }

  const nextValue = value[key]
  return isRecord(nextValue) ? nextValue : null
}

function getString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null
}

function getNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function getBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null
}

export function parseJsonObject(rawJson: string) {
  const trimmedJson = rawJson.trim()
  if (!trimmedJson) {
    return {
      error: "Enter JSON to continue.",
      value: null,
    } as const
  }

  let parsedJson: unknown

  try {
    parsedJson = JSON.parse(trimmedJson)
  } catch {
    return {
      error: "The JSON is not valid.",
      value: null,
    } as const
  }

  if (!isRecord(parsedJson)) {
    return {
      error: "The JSON must decode to an object.",
      value: null,
    } as const
  }

  return {
    error: null,
    value: parsedJson,
  } as const
}

export function parseJsonStringRecord(rawJson: string): {
  error: string | null
  value: Record<string, string> | null
} {
  const parsed = parseJsonObject(rawJson)
  if (parsed.error || !parsed.value) {
    return {
      error: parsed.error,
      value: null,
    }
  }

  const normalized: Record<string, string> = {}
  for (const [key, value] of Object.entries(parsed.value)) {
    if (typeof key !== "string" || typeof value !== "string") {
      return {
        error: "Topic type hints must map strings to strings.",
        value: null,
      }
    }

    const normalizedKey = key.trim()
    const normalizedValue = value.trim()
    if (!normalizedKey || !normalizedValue) {
      return {
        error: "Topic type hints entries must be non-empty.",
        value: null,
      }
    }

    normalized[normalizedKey] = normalizedValue
  }

  return {
    error: null,
    value: normalized,
  }
}

export function stringifyJson(value: unknown, space = 2) {
  return JSON.stringify(value, null, space)
}

export function summarizeConversionSpec(spec: ConversionSpec | null | undefined): ConversionSpecSummary {
  if (!spec) {
    return {
      featureCount: 0,
      labelPrimary: null,
      outputCompression: null,
      outputFormat: null,
      rowStrategyKind: null,
      schemaName: null,
      schemaVersion: null,
      writeManifest: null,
    }
  }

  const schema = getRecord(spec, "schema")
  const rowStrategy = getRecord(spec, "row_strategy") ?? getRecord(spec, "assembly")
  const output = getRecord(spec, "output")
  const labels = getRecord(spec, "labels")
  const features = getRecord(spec, "features")

  return {
    featureCount: features ? Object.keys(features).length : 0,
    labelPrimary: labels ? getString(labels.primary) : null,
    outputCompression: output ? getString(output.compression) : null,
    outputFormat: output ? getString(output.format) : null,
    rowStrategyKind: rowStrategy ? getString(rowStrategy.kind) : null,
    schemaName: schema ? getString(schema.name) : null,
    schemaVersion: schema ? getNumber(schema.version) : null,
    writeManifest: getBoolean(spec.write_manifest),
  }
}

export function resolveSavedConfigSpec(detail: SavedConversionConfigDetailResponse): ConversionSpec | null {
  return detail.resolved_spec ?? detail.resolved_spec_document?.spec ?? null
}

export function getInspectionTopicNames(inspection: InspectionResult | null | undefined) {
  return Object.keys(inspection?.topics ?? {})
}

export function summarizeInspectionTopic(topic: TopicInspectionResult) {
  return {
    candidateCount: Object.keys(topic.field_candidates).length,
    firstCandidatePaths: Object.keys(topic.field_candidates).slice(0, 3),
    sampleCount: topic.sampled_message_count,
    warningCount: topic.warnings.length,
  }
}

export function normalizeTopicList(topics: string[]) {
  return Array.from(new Set(topics.map((topic) => topic.trim()).filter(Boolean)))
}
