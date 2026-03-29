"use client";

import * as React from "react";
import {
  ChevronDown,
  Database,
  ListFilter,
  RefreshCw,
  Search,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { OutputsTable, OutputsCards } from "@/components/output-table";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/sonner";
import {
  useAssets,
  useCreateOutputAction,
  useOutputs,
} from "@/hooks/use-backend";
import type {
  OutputActionDetail,
  OutputAvailability,
  OutputDetail,
  OutputFormat,
  OutputRole,
  OutputsQuery,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/api";
import {
  useAppPathname as usePathname,
  useAppRouter as useRouter,
  useAppSearchParams as useSearchParams,
} from "@/lib/app-routing";
import {
  formatCount,
  formatOutputAvailability,
  formatOutputFormat,
  formatOutputRole,
  isWorkflowActiveStatus,
} from "@/lib/format";
import { buildOutputDetailHref } from "@/lib/navigation";
import type { ActiveFilterChip } from "@/lib/types";
import { cn } from "@/lib/utils";

const OUTPUT_FORMAT_OPTIONS: OutputFormat[] = ["parquet", "tfrecord", "json", "jsonl", "unknown"];
const OUTPUT_ROLE_OPTIONS: OutputRole[] = ["dataset", "manifest", "sidecar"];
const OUTPUT_AVAILABILITY_OPTIONS: OutputAvailability[] = ["ready", "missing", "invalid"];
const OUTPUT_PRESET_OPTIONS = [
  {
    description: "Show dataset artifacts that are currently available on disk.",
    label: "Ready datasets",
    value: "ready_datasets",
  },
  {
    description: "Focus on outputs with queued or running backend actions.",
    label: "Active compute",
    value: "active_compute",
  },
  {
    description: "Show JSON and JSONL sidecars such as manifests and summaries.",
    label: "JSON sidecars",
    value: "json_sidecars",
  },
] as const;

type OutputPreset = (typeof OUTPUT_PRESET_OPTIONS)[number]["value"];

function parseOutputSelection(value: string | null) {
  return Array.from(
    new Set(
      (value ?? "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function buildOutputsQuery(searchParams: URLSearchParams): OutputsQuery {
  const search = searchParams.get("search")?.trim() ?? "";
  const format = searchParams.get("format")?.trim() ?? "";
  const role = searchParams.get("role")?.trim() ?? "";
  const assetId = searchParams.get("asset_id")?.trim() ?? "";
  const availability = searchParams.get("availability")?.trim() ?? "";
  const conversionId = searchParams.get("conversion_id")?.trim() ?? "";

  return {
    asset_id: assetId || undefined,
    availability: availability || undefined,
    conversion_id: conversionId || undefined,
    format: format || undefined,
    limit: 500,
    role: role || undefined,
    search: search || undefined,
  };
}

function applyOutputPreset(outputs: OutputDetail[], preset: OutputPreset | null) {
  if (!preset) {
    return outputs;
  }

  if (preset === "ready_datasets") {
    return outputs.filter(
      (output) => output.role === "dataset" && output.availability_status === "ready",
    );
  }

  if (preset === "active_compute") {
    return outputs.filter(
      (output) =>
        output.latest_action !== null && isWorkflowActiveStatus(output.latest_action.status),
    );
  }

  if (preset === "json_sidecars") {
    return outputs.filter(
      (output) =>
        output.format === "json" ||
        output.format === "jsonl" ||
        output.role === "manifest" ||
        output.role === "sidecar",
    );
  }

  return outputs;
}

function OutputsPageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-9 w-44" />
      <Skeleton className="h-28 rounded-xl" />
      <Skeleton className="h-[640px] rounded-xl" />
    </div>
  );
}

export function OutputsPageFallback() {
  return <OutputsPageSkeleton />;
}

export function OutputsPage() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  const { isCreating, trigger } = useCreateOutputAction();

  const query = React.useMemo(() => buildOutputsQuery(searchParams), [searchParams]);
  const presetValue = searchParams.get("preset")?.trim() ?? "";
  const preset = React.useMemo(
    () =>
      OUTPUT_PRESET_OPTIONS.some((option) => option.value === presetValue)
        ? (presetValue as OutputPreset)
        : null,
    [presetValue],
  );
  const selectedOutputId = searchParams.get("output")?.trim() ?? "";
  const imagePayloadContract = searchParams.get("image_payload_contract")?.trim() ?? "";
  const selectedOutputIds = React.useMemo(
    () => parseOutputSelection(searchParams.get("selection")),
    [searchParams],
  );
  const [searchInput, setSearchInput] = React.useState(query.search ?? "");
  const [isFiltersOpen, setIsFiltersOpen] = React.useState(false);

  const outputsResponse = useOutputs(query);
  const assetsResponse = useAssets();

  const baseOutputs = React.useMemo(() => outputsResponse.data ?? [], [outputsResponse.data]);
  const outputs = React.useMemo(
    () => applyOutputPreset(baseOutputs, preset),
    [baseOutputs, preset],
  );
  const selectedOutputIdsSet = React.useMemo(
    () => new Set(selectedOutputIds),
    [selectedOutputIds],
  );
  const selectedOutputs = React.useMemo(
    () => outputs.filter((output) => selectedOutputIdsSet.has(output.id)),
    [outputs, selectedOutputIdsSet],
  );
  const currentHref = React.useMemo(() => {
    const queryString = searchParams.toString();
    return queryString ? `${pathname}?${queryString}` : pathname;
  }, [pathname, searchParams]);
  const assetsById = React.useMemo(
    () => new Map((assetsResponse.data ?? []).map((asset) => [asset.id, asset])),
    [assetsResponse.data],
  );
  const visibleOutputIds = React.useMemo(
    () => new Set(outputs.map((output) => output.id)),
    [outputs],
  );
  const activeActionCount = outputs.filter(
    (output) =>
      output.latest_action !== null && isWorkflowActiveStatus(output.latest_action.status),
  ).length;
  const allVisibleSelected = outputs.length > 0 && selectedOutputs.length === outputs.length;
  const activeFilterChips: ActiveFilterChip[] = [];

  if (query.search) {
    activeFilterChips.push({
      key: "search",
      label: `Search: ${query.search}`,
      updates: { output: null, search: null, selection: null },
    });
  }

  if (query.format) {
    activeFilterChips.push({
      key: "format",
      label: `Format: ${formatOutputFormat(query.format as OutputFormat)}`,
      updates: { format: null, output: null, selection: null },
    });
  }

  if (query.role) {
    activeFilterChips.push({
      key: "role",
      label: `Role: ${formatOutputRole(query.role as OutputRole)}`,
      updates: { output: null, role: null, selection: null },
    });
  }

  if (query.availability) {
    activeFilterChips.push({
      key: "availability",
      label: `Availability: ${formatOutputAvailability(query.availability as OutputAvailability)}`,
      updates: { availability: null, output: null, selection: null },
    });
  }

  if (query.asset_id) {
    activeFilterChips.push({
      key: "asset_id",
      label: `Asset: ${query.asset_id}`,
      updates: { asset_id: null, output: null, selection: null },
    });
  }

  if (query.conversion_id) {
    activeFilterChips.push({
      key: "conversion_id",
      label: `Conversion: ${query.conversion_id}`,
      updates: { conversion_id: null, output: null, selection: null },
    });
  }

  if (imagePayloadContract) {
    activeFilterChips.push({
      key: "image_payload_contract",
      label: `Image payload: ${imagePayloadContract}`,
      updates: { image_payload_contract: null, output: null, selection: null },
    });
  }

  if (preset) {
    activeFilterChips.push({
      key: "preset",
      label: `Preset: ${OUTPUT_PRESET_OPTIONS.find((option) => option.value === preset)?.label ?? preset}`,
      updates: { output: null, preset: null, selection: null },
    });
  }

  const hasAppliedFilters = activeFilterChips.length > 0;
  const updateFilters = React.useCallback(
    (updates: Record<string, string | null>) => {
      const nextParams = new URLSearchParams(searchParams.toString());

      for (const [key, value] of Object.entries(updates)) {
        const normalizedValue = value?.trim() ?? "";

        if (!normalizedValue) {
          nextParams.delete(key);
        } else {
          nextParams.set(key, normalizedValue);
        }
      }

      const nextQuery = nextParams.toString();
      const nextHref = nextQuery ? `${pathname}?${nextQuery}` : pathname;

      router.replace(nextHref, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  React.useEffect(() => {
    setSearchInput(query.search ?? "");
  }, [query.search]);

  React.useEffect(() => {
    if (hasAppliedFilters) {
      setIsFiltersOpen(true);
    }
  }, [hasAppliedFilters]);

  const clearWorkspaceFilters = React.useCallback(() => {
    updateFilters({
      asset_id: null,
      availability: null,
      conversion_id: null,
      format: null,
      image_payload_contract: null,
      output: null,
      preset: null,
      role: null,
      search: null,
      selection: null,
    });
  }, [updateFilters]);

  React.useEffect(() => {
    if ((outputsResponse.isLoading && !outputsResponse.data) || selectedOutputIds.length === 0) {
      return;
    }

    const trimmedSelection = selectedOutputIds.filter((outputId) => visibleOutputIds.has(outputId));
    if (trimmedSelection.length !== selectedOutputIds.length) {
      updateFilters({
        selection: trimmedSelection.length > 0 ? trimmedSelection.join(",") : null,
      });
    }
  }, [
    outputsResponse.data,
    outputsResponse.isLoading,
    selectedOutputIds,
    updateFilters,
    visibleOutputIds,
  ]);

  React.useEffect(() => {
    if (activeActionCount === 0) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void outputsResponse.mutate();
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, [activeActionCount, outputsResponse]);

  function onSearchSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateFilters({
      output: null,
      search: searchInput,
      selection: null,
    });
  }

  function onClearSearch() {
    setSearchInput("");
    updateFilters({
      output: null,
      search: null,
      selection: null,
    });
  }

  function onToggleOutputSelection(outputId: string) {
    const nextSelection = selectedOutputIdsSet.has(outputId)
      ? selectedOutputIds.filter((currentId) => currentId !== outputId)
      : [...selectedOutputIds, outputId];

    updateFilters({
      selection: nextSelection.length > 0 ? nextSelection.join(",") : null,
    });
  }

  function onToggleAllVisible() {
    updateFilters({
      selection: allVisibleSelected ? null : outputs.map((output) => output.id).join(","),
    });
  }

  async function onRefreshMetadata(outputsToRefresh: OutputDetail[]) {
    if (outputsToRefresh.length === 0) {
      return;
    }

    try {
      const createdActions: OutputActionDetail[] = [];

      for (const output of outputsToRefresh) {
        const action = await trigger(output.id, {
          action_type: "refresh_metadata",
          config: {
            reason:
              outputsToRefresh.length > 1
                ? "batch_refresh_from_outputs_page"
                : "manual_refresh_from_outputs_page",
          },
        });
        createdActions.push(action);
      }

      const firstOutput = outputsToRefresh[0];
      toast.success(
        outputsToRefresh.length === 1
          ? `Metadata refreshed for ${firstOutput?.file_name ?? "the selected output"}.`
          : `Metadata refreshed for ${outputsToRefresh.length} selected outputs.`,
      );
    } catch (error) {
      toast.error("Could not refresh output metadata", {
        description: getErrorMessage(error),
      });
    }
  }

  if (outputsResponse.isLoading && !outputsResponse.data) {
    return <OutputsPageSkeleton />;
  }

  if (outputsResponse.error) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertTitle>Could not load outputs</AlertTitle>
          <AlertDescription>{getErrorMessage(outputsResponse.error)}</AlertDescription>
        </Alert>
        <div>
          <Button onClick={() => void outputsResponse.mutate()} type="button" variant="outline">
            Try again
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">Outputs</h1>
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                {formatCount(outputs.length, "output")}
              </span>
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                {formatCount(activeActionCount, "active action")}
              </span>
            </div>
            <p className="max-w-3xl text-sm text-muted-foreground">Output artifacts and actions.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={outputsResponse.isLoading}
              onClick={() => void outputsResponse.mutate()}
              size="sm"
              type="button"
              variant="outline"
            >
              <RefreshCw className="size-4" />
              Refresh
            </Button>
          </div>
        </div>
      </section>

      <Card className="flex-1">
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Database className="size-4" />
                Output catalog
              </CardTitle>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="h-6" variant="secondary">
                {formatCount(outputs.length, "result")}
              </Badge>
              {selectedOutputs.length > 0 ? (
                <>
                  <Badge className="h-6" variant="outline">
                    {selectedOutputs.length} selected
                  </Badge>
                  <Button
                    disabled={isCreating}
                    onClick={() => void onRefreshMetadata(selectedOutputs)}
                    size="sm"
                    type="button"
                  >
                    <Wrench className="size-3.5" />
                    Batch refresh metadata
                  </Button>
                  <Button
                    disabled
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    <Sparkles className="size-3.5" />
                    Batch VLM tagging soon
                  </Button>
                  <Button
                    onClick={() => updateFilters({ selection: null })}
                    size="sm"
                    type="button"
                    variant="ghost"
                  >
                    Clear selection
                  </Button>
                </>
              ) : null}
              {imagePayloadContract ? (
                <Alert>
                  <AlertTitle>Conversion payload context</AlertTitle>
                  <AlertDescription>
                    These outputs were opened from a conversion using the
                    <span className="mx-1 font-mono">{imagePayloadContract}</span>
                    image payload contract. Use output previews to confirm loader expectations.
                  </AlertDescription>
                </Alert>
              ) : null}
              <Button
                aria-expanded={isFiltersOpen}
                onClick={() => setIsFiltersOpen((current) => !current)}
                size="sm"
                type="button"
                variant="outline"
              >
                <ListFilter className="size-4" />
                Search & filters{hasAppliedFilters ? ` (${activeFilterChips.length})` : ""}
                <ChevronDown className={cn("size-4 transition-transform", isFiltersOpen && "rotate-180")} />
              </Button>
            </div>
          </div>

          <div
            className={cn(
              "grid transition-all duration-200 ease-out",
              isFiltersOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0 pointer-events-none",
            )}
          >
            <div className="min-h-0 overflow-hidden">
              <div className="space-y-4 rounded-xl border bg-muted/20 p-4">
                <form className="flex flex-col gap-3 lg:flex-row" onSubmit={onSearchSubmit}>
                  <div className="flex-1">
                    <label className="mb-2 block text-xs uppercase tracking-wide text-muted-foreground" htmlFor="outputs-search">
                      Search
                    </label>
                    <div className="flex gap-2">
                      <Input
                        id="outputs-search"
                        onChange={(event) => setSearchInput(event.target.value)}
                        placeholder="Search file name, path, format, or conversion ID"
                        value={searchInput}
                      />
                      <Button size="sm" type="submit" variant="outline">
                        <Search className="size-4" />
                        Search
                      </Button>
                      {(searchInput.length > 0 || (query.search ?? "").length > 0) && (
                        <Button onClick={onClearSearch} size="sm" type="button" variant="ghost">
                          <X className="size-4" />
                          Clear
                        </Button>
                      )}
                    </div>
                  </div>
                </form>

                <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
                  <div className="space-y-2">
                    <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="outputs-format">
                      Format
                    </label>
                    <NativeSelect
                      id="outputs-format"
                      onChange={(event) =>
                        updateFilters({
                          format: event.target.value || null,
                          output: null,
                          selection: null,
                        })
                      }
                      value={query.format ?? ""}
                    >
                      <option value="">All formats</option>
                      {OUTPUT_FORMAT_OPTIONS.map((format) => (
                        <option key={format} value={format}>
                          {formatOutputFormat(format)}
                        </option>
                      ))}
                    </NativeSelect>
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="outputs-role">
                      Role
                    </label>
                    <NativeSelect
                      id="outputs-role"
                      onChange={(event) =>
                        updateFilters({
                          output: null,
                          role: event.target.value || null,
                          selection: null,
                        })
                      }
                      value={query.role ?? ""}
                    >
                      <option value="">All roles</option>
                      {OUTPUT_ROLE_OPTIONS.map((role) => (
                        <option key={role} value={role}>
                          {formatOutputRole(role)}
                        </option>
                      ))}
                    </NativeSelect>
                  </div>
                  <div className="space-y-2">
                    <label
                      className="text-xs uppercase tracking-wide text-muted-foreground"
                      htmlFor="outputs-availability"
                    >
                      Availability
                    </label>
                    <NativeSelect
                      id="outputs-availability"
                      onChange={(event) =>
                        updateFilters({
                          availability: event.target.value || null,
                          output: null,
                          selection: null,
                        })
                      }
                      value={query.availability ?? ""}
                    >
                      <option value="">All</option>
                      {OUTPUT_AVAILABILITY_OPTIONS.map((availability) => (
                        <option key={availability} value={availability}>
                          {formatOutputAvailability(availability)}
                        </option>
                      ))}
                    </NativeSelect>
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs uppercase tracking-wide text-muted-foreground" htmlFor="outputs-asset">
                      Asset ID
                    </label>
                    <Input
                      id="outputs-asset"
                      onChange={(event) =>
                        updateFilters({ asset_id: event.target.value, output: null, selection: null })
                      }
                      placeholder="Filter to one asset"
                      value={query.asset_id ?? ""}
                    />
                  </div>
                  <div className="space-y-2">
                    <label
                      className="text-xs uppercase tracking-wide text-muted-foreground"
                      htmlFor="outputs-conversion"
                    >
                      Conversion ID
                    </label>
                    <Input
                      id="outputs-conversion"
                      onChange={(event) =>
                        updateFilters({
                          conversion_id: event.target.value,
                          output: null,
                          selection: null,
                        })
                      }
                      placeholder="Filter to one conversion"
                      value={query.conversion_id ?? ""}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Common slices</p>
                  <div className="flex flex-wrap gap-2">
                    {OUTPUT_PRESET_OPTIONS.map((option) => {
                      const isActive = preset === option.value;

                      return (
                        <Button
                          key={option.value}
                          onClick={() =>
                            updateFilters({
                              output: null,
                              preset: isActive ? null : option.value,
                              selection: null,
                            })
                          }
                          size="sm"
                          type="button"
                          variant={isActive ? "secondary" : "outline"}
                        >
                          {option.label}
                        </Button>
                      );
                    })}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {preset
                      ? OUTPUT_PRESET_OPTIONS.find((option) => option.value === preset)?.description
                      : "Presets are URL-backed, so you can share common output slices without rebuilding the filters each time."}
                  </p>
                </div>

                {hasAppliedFilters ? (
                  <div className="flex flex-wrap items-center gap-2">
                    {activeFilterChips.map((filter) => (
                      <Button
                        key={filter.key}
                        onClick={() => {
                          if (filter.key === "search") {
                            setSearchInput("");
                          }
                          updateFilters(filter.updates!);
                        }}
                        size="xs"
                        type="button"
                        variant="outline"
                      >
                        {filter.label}
                        <X className="size-3" />
                      </Button>
                    ))}
                    <Button onClick={clearWorkspaceFilters} size="xs" type="button" variant="ghost">
                      Clear filters
                    </Button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {outputs.length === 0 ? (
            <EmptyState
              action={
                hasAppliedFilters ? (
                  <Button onClick={clearWorkspaceFilters} type="button" variant="outline">
                    Clear filters
                  </Button>
                ) : undefined
              }
              description={
                hasAppliedFilters
                  ? "Try clearing one or more filters to see outputs from other conversion runs."
                  : "Run a conversion and its registered output artifacts will appear here for inspection."
              }
              title={hasAppliedFilters ? "No outputs match these filters" : "No outputs yet"}
            />
          ) : (
            <>
              <OutputsTable
                allVisibleSelected={allVisibleSelected}
                assetsById={assetsById}
                currentHref={currentHref}
                isRefreshing={isCreating}
                onRefreshMetadata={onRefreshMetadata}
                onSelectOutput={(outputId) => router.push(buildOutputDetailHref(outputId, currentHref))}
                onToggleAllVisible={onToggleAllVisible}
                onToggleOutputSelection={onToggleOutputSelection}
                outputs={outputs}
                selectedOutputId={selectedOutputId}
                selectedOutputIds={selectedOutputIdsSet}
              />
              <OutputsCards
                assetsById={assetsById}
                currentHref={currentHref}
                isRefreshing={isCreating}
                onRefreshMetadata={onRefreshMetadata}
                onSelectOutput={(outputId) => router.push(buildOutputDetailHref(outputId, currentHref))}
                onToggleOutputSelection={onToggleOutputSelection}
                outputs={outputs}
                selectedOutputIds={selectedOutputIdsSet}
              />
            </>
          )}
        </CardContent>
      </Card>

    </div>
  );
}
