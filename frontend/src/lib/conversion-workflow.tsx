"use client";

import * as React from "react";

import { formatSentenceCase } from "@/lib/format";
import {
  type ConversionCreateRequest,
  type ConversionFormat,
  type ParquetConversionOutputRequest,
  type ResampleMethod,
  type TFRecordConversionOutputRequest,
} from "@/lib/api";

export type ParquetCompression = NonNullable<ParquetConversionOutputRequest["compression"]>;
export type TFRecordCompression = NonNullable<TFRecordConversionOutputRequest["compression"]>;
export type MappingMode = "auto" | "custom";

export const PARQUET_COMPRESSION_OPTIONS: ParquetCompression[] = [
  "none",
  "snappy",
  "gzip",
  "brotli",
  "lz4",
  "zstd",
];

export const TFRECORD_COMPRESSION_OPTIONS: TFRecordCompression[] = ["none", "gzip"];
export const RESAMPLE_METHOD_OPTIONS: ResampleMethod[] = ["downsample", "interpolate"];

export interface ConversionFormState {
  mapping: {
    customJson: string;
    mode: MappingMode;
  };
  output: {
    format: ConversionFormat;
    parquetCompression: ParquetCompression;
    tfrecordCompression: TFRecordCompression;
  };
  resample: {
    enabled: boolean;
    freqHz: string;
    method: ResampleMethod;
  };
  writeManifest: boolean;
}

export function createDefaultFormState(): ConversionFormState {
  return {
    mapping: {
      customJson: "",
      mode: "auto",
    },
    output: {
      format: "parquet",
      parquetCompression: "snappy",
      tfrecordCompression: "none",
    },
    resample: {
      enabled: false,
      freqHz: "10",
      method: "downsample",
    },
    writeManifest: true,
  };
}

export function formatMappingSummary(mode: MappingMode) {
  return mode === "custom" ? "Custom JSON mapping" : "Automatic mapping";
}

export function parseCustomMapping(customJson: string) {
  const trimmedJson = customJson.trim();
  if (!trimmedJson) {
    return {
      error: "Enter a mapping JSON object or switch back to automatic mapping.",
      value: null,
    } as const;
  }

  let parsedJson: unknown;

  try {
    parsedJson = JSON.parse(trimmedJson);
  } catch {
    return {
      error: "Custom mapping must be valid JSON.",
      value: null,
    } as const;
  }

  if (!parsedJson || typeof parsedJson !== "object" || Array.isArray(parsedJson)) {
    return {
      error: "Custom mapping must be a JSON object of output fields to topic lists.",
      value: null,
    } as const;
  }

  const mappingEntries = Object.entries(parsedJson);
  if (mappingEntries.length === 0) {
    return {
      error: "Custom mapping must include at least one output field.",
      value: null,
    } as const;
  }

  const normalizedMapping: Record<string, string[]> = {};

  for (const [targetField, sourceTopics] of mappingEntries) {
    if (!targetField.trim()) {
      return {
        error: "Custom mapping field names must be non-empty.",
        value: null,
      } as const;
    }

    if (!Array.isArray(sourceTopics) || sourceTopics.length === 0) {
      return {
        error: `Mapping for "${targetField}" must be a non-empty list of topics.`,
        value: null,
      } as const;
    }

    const normalizedTopics = sourceTopics.map((topic) => (typeof topic === "string" ? topic.trim() : ""));
    if (normalizedTopics.some((topic) => topic.length === 0)) {
      return {
        error: `Mapping for "${targetField}" contains an empty topic name.`,
        value: null,
      } as const;
    }

    normalizedMapping[targetField.trim()] = normalizedTopics;
  }

  return {
    error: null,
    value: normalizedMapping,
  } as const;
}

export function buildConversionPayload(
  assets: { id: string }[],
  formState: ConversionFormState,
): ConversionCreateRequest {
  const payload: ConversionCreateRequest = {
    asset_ids: assets.map((asset) => asset.id),
    output:
      formState.output.format === "parquet"
        ? {
            compression: formState.output.parquetCompression,
            format: "parquet",
          }
        : {
            compression: formState.output.tfrecordCompression,
            format: "tfrecord",
            null_encoding: "presence_flag",
            payload_encoding: "typed_features",
          },
    write_manifest: formState.writeManifest,
  };

  if (formState.mapping.mode === "custom") {
    const parsedMapping = parseCustomMapping(formState.mapping.customJson);
    if (parsedMapping.value) {
      payload.mapping = parsedMapping.value;
    }
  }

  if (formState.resample.enabled) {
    payload.resample = {
      freq_hz: Number(formState.resample.freqHz),
      method: formState.resample.method,
    };
  }

  return payload;
}

export function SummaryField({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium text-foreground">{value}</dd>
    </div>
  );
}

export function formatCompressionLabel(compression: string) {
  return formatSentenceCase(compression);
}
