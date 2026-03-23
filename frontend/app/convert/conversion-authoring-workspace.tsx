"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  Copy,
  FileJson2,
  LoaderCircle,
  Play,
  RefreshCcw,
  Save,
  Sparkles,
  TriangleAlert,
} from "lucide-react"

import { EmptyState } from "@/components/empty-state"
import { WorkflowStatusBadge } from "@/components/workflow-status-badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NativeSelect } from "@/components/ui/native-select"
import { Switch } from "@/components/ui/switch"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "@/components/ui/sonner"
import {
  useAssets,
  useBackendCache,
  useConversion,
  useConversionAuthoringCapabilities,
  useSavedConversionConfig,
  useSavedConversionConfigs,
} from "@/hooks/use-backend"
import { useCreateConversion } from "@/hooks/use-create-conversion"
import {
  draftConversion,
  duplicateConversionConfig,
  createConversionConfig,
  getErrorMessage,
  inspectConversion,
  previewConversion,
  updateConversionConfig,
  BackendApiError,
  type ConversionCreateRequest,
  type ConversionDraftRequest,
  type ConversionDraftResponse,
  type ConversionFormat,
  type ConversionInspectionRequest,
  type ConversionInspectionResponse,
  type ConversionPreviewRequest,
  type ConversionPreviewResponse,
  type DecodeFailurePolicy,
  type SavedConversionConfigSummaryResponse,
} from "@/lib/api"
import {
  formatDateTime,
  formatFileSize,
  formatSentenceCase,
  isWorkflowActiveStatus,
} from "@/lib/format"
import { buildOutputsHref } from "@/lib/outputs"
import {
  buildConversionCreateHref,
  buildConversionUseHref,
  buildJobDetailHref,
  resolveReturnHref,
} from "@/lib/navigation"
import {
  normalizeTopicList,
  parseJsonObject,
  parseJsonStringRecord,
  resolveSavedConfigSpec,
  stringifyJson,
  summarizeConversionSpec,
  summarizeInspectionTopic,
} from "@/lib/conversion-authoring"
import {
  getImagePayloadContract,
  normalizeOutputContractCapabilities,
} from "@/lib/conversion-representation"

type NoticeState = {
  description?: string
  title: string
  tone: "error" | "info"
} | null

type ConfigDialogMode = "create" | "duplicate" | "update" | null

type SpecFormState = {
  includePreview: boolean
  labelFeature: string
  maxFeaturesPerTopic: string
  outputCompression: string
  outputFormat: ConversionFormat
  previewRows: string
  schemaName: string
  schemaVersion: string
  selectedTopics: string[]
  triggerTopic: string
}

type InspectionFormState = {
  maxDepth: string
  maxSequenceItems: string
  onFailure: DecodeFailurePolicy
  sampleN: string
  topicTypeHints: string
}

export type ConversionWorkspaceMode = "create" | "use"
type CreateWizardStep = "source" | "inspect" | "draft" | "spec" | "preview"

const CREATE_WIZARD_STEPS: Array<{
  id: CreateWizardStep
  label: string
}> = [
  {
    id: "source",
    label: "Source",
  },
  {
    id: "inspect",
    label: "Inspect",
  },
  {
    id: "draft",
    label: "Draft",
  },
  {
    id: "spec",
    label: "Spec",
  },
  {
    id: "preview",
    label: "Preview",
  },
]

const DEFAULT_INSPECTION_FORM: InspectionFormState = {
  maxDepth: "4",
  maxSequenceItems: "4",
  onFailure: "warn",
  sampleN: "8",
  topicTypeHints: "",
}

const DEFAULT_SPEC_FORM: SpecFormState = {
  includePreview: true,
  labelFeature: "",
  maxFeaturesPerTopic: "2",
  outputCompression: "none",
  outputFormat: "tfrecord",
  previewRows: "5",
  schemaName: "draft_conversion",
  schemaVersion: "1",
  selectedTopics: [],
  triggerTopic: "",
}

function parseAssetIds(rawAssetIds: string | null | undefined) {
  return Array.from(
    new Set(
      (rawAssetIds ?? "")
        .split(",")
        .map((assetId) => assetId.trim())
        .filter(Boolean)
    )
  )
}

function parseOptionalTopicTypeHints(rawJson: string) {
  const trimmedJson = rawJson.trim()
  if (!trimmedJson) {
    return {
      error: null,
      value: null,
    } as const
  }

  return parseJsonStringRecord(trimmedJson)
}

function buildWorkspaceMetadata(
  assetIds: string[],
  sourceAssetId: string | null
) {
  return {
    asset_ids: assetIds,
    authoring_surface: "frontend",
    source_asset_id: sourceAssetId,
  }
}

function getConfigStatusBadgeVariant(
  status: SavedConversionConfigSummaryResponse["status"]
) {
  if (status === "invalid") {
    return "destructive" as const
  }

  if (status === "needs_migration") {
    return "secondary" as const
  }

  return "outline" as const
}

function getConfigStatusClasses(
  status: SavedConversionConfigSummaryResponse["status"]
) {
  if (status === "invalid") {
    return "border-destructive/30 bg-destructive/10 text-destructive"
  }

  if (status === "needs_migration") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200"
  }

  return "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200"
}

function getTopicHintCount(rawJson: string) {
  const parsed = parseOptionalTopicTypeHints(rawJson)
  if (parsed.error || !parsed.value) {
    return null
  }

  return Object.keys(parsed.value).length
}

function CreateWizardBreadcrumb({
  currentStep,
  onStepChange,
}: {
  currentStep: CreateWizardStep
  onStepChange: (step: CreateWizardStep) => void
}) {
  const currentStepIndex = CREATE_WIZARD_STEPS.findIndex(
    (step) => step.id === currentStep
  )

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {CREATE_WIZARD_STEPS.map((step, index) => {
          const isActive = index === currentStepIndex
          const isComplete = index < currentStepIndex
          const canNavigateBack = index < currentStepIndex

          return (
            <React.Fragment key={step.id}>
              <BreadcrumbItem>
                {isActive ? (
                  <BreadcrumbPage>{step.label}</BreadcrumbPage>
                ) : canNavigateBack ? (
                  <BreadcrumbLink asChild>
                    <button
                      className="transition-colors hover:text-foreground"
                      onClick={() => onStepChange(step.id)}
                      type="button"
                    >
                      {step.label}
                    </button>
                  </BreadcrumbLink>
                ) : (
                  <span
                    className={
                      isComplete
                        ? "transition-colors hover:text-foreground"
                        : "text-muted-foreground/60"
                    }
                  >
                    {step.label}
                  </span>
                )}
              </BreadcrumbItem>
              {index < CREATE_WIZARD_STEPS.length - 1 ? (
                <BreadcrumbSeparator />
              ) : null}
            </React.Fragment>
          )
        })}
      </BreadcrumbList>
    </Breadcrumb>
  )
}

function ConversionStatusCard({
  activeConversion,
  currentHref,
  isRefreshing,
  onNewConversion,
}: {
  activeConversion: NonNullable<ReturnType<typeof useConversion>["data"]>
  currentHref: string
  isRefreshing: boolean
  onNewConversion: () => void
}) {
  const hasShownCreatedToast = React.useRef<string | null>(null)
  const effectiveRepresentationPolicy =
    activeConversion.representation_policy ??
    activeConversion.job.representation_policy ??
    null

  React.useEffect(() => {
    if (hasShownCreatedToast.current === activeConversion.id) {
      return
    }

    hasShownCreatedToast.current = activeConversion.id

    toast.success("Conversion created", {
      description: `The backend created conversion ${activeConversion.id} with status ${activeConversion.status}.`,
    })
  }, [activeConversion.id, activeConversion.status])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Conversion status</CardTitle>
          <CardDescription>
            Initial handoff from the backend-managed conversion workflow.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                Conversion status
              </dt>
              <dd>
                <WorkflowStatusBadge status={activeConversion.status} />
              </dd>
            </div>
            <div className="space-y-1">
              <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                Job status
              </dt>
              <dd>
                <WorkflowStatusBadge status={activeConversion.job.status} />
              </dd>
            </div>
            <div className="space-y-1">
              <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                Created
              </dt>
              <dd className="text-sm font-medium text-foreground">
                {formatDateTime(activeConversion.created_at)}
              </dd>
            </div>
            <div className="space-y-1">
              <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                Job ID
              </dt>
              <dd className="font-mono text-xs break-all text-foreground">
                {activeConversion.job_id}
              </dd>
            </div>
            <div className="space-y-1 sm:col-span-2">
              <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                Output path
              </dt>
              <dd className="text-sm font-medium break-all text-foreground">
                {activeConversion.output_path ?? "Not available yet"}
              </dd>
            </div>
            <div className="space-y-1 sm:col-span-2">
              <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                Selected assets
              </dt>
              <dd className="text-sm font-medium text-foreground">
                {activeConversion.asset_ids.length} asset
                {activeConversion.asset_ids.length === 1 ? "" : "s"}
              </dd>
            </div>
          </dl>

          {activeConversion.error_message ? (
            <Alert variant="destructive">
              <TriangleAlert className="size-4" />
              <AlertTitle>Execution error</AlertTitle>
              <AlertDescription>
                {activeConversion.error_message}
              </AlertDescription>
            </Alert>
          ) : null}

          <div className="space-y-2">
            <p className="text-xs tracking-wide text-muted-foreground uppercase">
              Output files
            </p>
            {activeConversion.output_files.length > 0 ? (
              <div className="space-y-2">
                {activeConversion.output_files.map((outputFile) => (
                  <div
                    key={outputFile}
                    className="rounded-lg border bg-muted/20 px-3 py-2 text-sm break-all text-foreground"
                  >
                    {outputFile}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Output files have not been reported yet. The linked job status
                above will update while this page stays open.
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              disabled={isRefreshing}
              onClick={onNewConversion}
              type="button"
              variant="outline"
            >
              New conversion
            </Button>
            <Button asChild type="button" variant="outline">
              <Link
                href={buildJobDetailHref(activeConversion.job_id, currentHref)}
              >
                Open job
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
            <Button asChild type="button" variant="outline">
              <Link
                href={buildOutputsHref({
                  conversionId: activeConversion.id,
                  imagePayloadContract: getImagePayloadContract(
                    effectiveRepresentationPolicy
                  ),
                })}
              >
                View outputs
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export function ConversionAuthoringWorkspaceFallback() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="h-9 w-48 rounded bg-muted" />
        <div className="h-5 w-full max-w-3xl rounded bg-muted" />
      </div>
      <Card>
        <CardContent className="space-y-4 p-6">
          <div className="h-24 rounded-xl bg-muted" />
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)]">
            <div className="h-[640px] rounded-xl bg-muted" />
            <div className="h-[640px] rounded-xl bg-muted" />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function SavedConfigDropdown({
  configs,
  onCreateNew,
  onSelectConfig,
  selectedConfig,
}: {
  configs: SavedConversionConfigSummaryResponse[]
  onCreateNew: () => void
  onSelectConfig: (configId: string) => void
  selectedConfig: SavedConversionConfigSummaryResponse | null
}) {
  const buttonLabel = selectedConfig?.name ?? "Choose saved config"

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          className="min-w-[16rem] justify-between"
          size="sm"
          type="button"
          variant="outline"
        >
          <span className="truncate">{buttonLabel}</span>
          <ChevronDown className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[19rem]">
        <DropdownMenuLabel>Saved configs</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {configs.length > 0 ? (
          <DropdownMenuRadioGroup
            onValueChange={onSelectConfig}
            value={selectedConfig?.id ?? ""}
          >
            {configs.map((config) => (
              <DropdownMenuRadioItem
                key={config.id}
                className="flex flex-col items-start gap-0.5 py-2"
                value={config.id}
              >
                <span className="font-medium text-foreground">
                  {config.name}
                </span>
                <span className="text-xs text-muted-foreground">
                  {config.spec_schema_name ?? "Unknown schema"}
                  {config.spec_schema_version !== null
                    ? ` v${config.spec_schema_version}`
                    : ""}
                </span>
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        ) : (
          <DropdownMenuItem disabled>No saved configs yet</DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={(event) => {
            event.preventDefault()
            onCreateNew()
          }}
        >
          New config
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function ConfigEditorDialog({
  description,
  dialogMode,
  isSubmitting,
  onDescriptionChange,
  onNameChange,
  name,
  open,
  onOpenChange,
  onSubmit,
}: {
  description: string
  dialogMode: ConfigDialogMode
  isSubmitting: boolean
  onDescriptionChange: (description: string) => void
  onNameChange: (name: string) => void
  name: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: () => void
}) {
  const title =
    dialogMode === "duplicate"
      ? "Duplicate saved config"
      : dialogMode === "update"
        ? "Update saved config"
        : "Save current spec"
  const actionLabel =
    dialogMode === "duplicate"
      ? "Duplicate"
      : dialogMode === "update"
        ? "Update"
        : "Save"

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Keep the form small and let the backend own the spec contract. Only
            the saved-config metadata is edited here.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="config-name">Name</Label>
            <Input
              id="config-name"
              onChange={(event) => onNameChange(event.target.value)}
              value={name}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="config-description">Description</Label>
            <Textarea
              id="config-description"
              onChange={(event) => onDescriptionChange(event.target.value)}
              value={description}
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            disabled={isSubmitting}
            onClick={() => onOpenChange(false)}
            type="button"
            variant="ghost"
          >
            Cancel
          </Button>
          <Button disabled={isSubmitting} onClick={onSubmit} type="button">
            {isSubmitting ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : null}
            {actionLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function ConversionAuthoringWorkspace({
  mode = "use",
}: {
  mode?: ConversionWorkspaceMode
}) {
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()
  const isCreateMode = mode === "create"
  const isUseMode = mode === "use"
  const {
    revalidateConversionDetail,
    revalidateConversions,
    revalidateJobs,
    revalidateOutputs,
    revalidateSavedConfigDetail,
    revalidateSavedConfigs,
  } = useBackendCache()
  const { isSubmitting, submit: submitConversion } = useCreateConversion()
  const assetsResponse = useAssets()
  const savedConfigsResponse = useSavedConversionConfigs()
  const capabilitiesResponse = useConversionAuthoringCapabilities()
  const [createdConversion, setCreatedConversion] = React.useState<NonNullable<
    ReturnType<typeof useConversion>["data"]
  > | null>(null)
  const [requestMessage, setRequestMessage] = React.useState<NoticeState>(null)
  const [sourceAssetId, setSourceAssetId] = React.useState(
    () => searchParams.get("source_asset_id")?.trim() ?? ""
  )
  const [selectedSavedConfigId, setSelectedSavedConfigId] = React.useState(
    () => searchParams.get("saved_config_id")?.trim() ?? ""
  )
  const [inspectionResponse, setInspectionResponse] =
    React.useState<ConversionInspectionResponse | null>(null)
  const [draftResponse, setDraftResponse] =
    React.useState<ConversionDraftResponse | null>(null)
  const [previewResponse, setPreviewResponse] =
    React.useState<ConversionPreviewResponse | null>(null)
  const [specText, setSpecText] = React.useState("")
  const [inspectionForm, setInspectionForm] =
    React.useState<InspectionFormState>(DEFAULT_INSPECTION_FORM)
  const [specForm, setSpecForm] =
    React.useState<SpecFormState>(DEFAULT_SPEC_FORM)
  const [configDialogMode, setConfigDialogMode] =
    React.useState<ConfigDialogMode>(null)
  const [configDialogName, setConfigDialogName] = React.useState("")
  const [configDialogDescription, setConfigDialogDescription] =
    React.useState("")
  const [isInspecting, setIsInspecting] = React.useState(false)
  const [isDrafting, setIsDrafting] = React.useState(false)
  const [isPreviewing, setIsPreviewing] = React.useState(false)
  const [isSavingConfig, setIsSavingConfig] = React.useState(false)
  const [isRunningSavedConfig, setIsRunningSavedConfig] = React.useState(false)
  const [createStep, setCreateStep] = React.useState<CreateWizardStep>("source")

  const assetIds = React.useMemo(
    () => parseAssetIds(searchParams.get("asset_ids")),
    [searchParams]
  )
  const assetIdSet = React.useMemo(() => new Set(assetIds), [assetIds])
  const queryConversionId = searchParams.get("conversion_id")?.trim() ?? ""
  const returnHref = resolveReturnHref(searchParams.get("from"), "/inventory")
  const currentHref = React.useMemo(() => {
    const query = searchParams.toString()
    return query ? `${pathname}?${query}` : pathname
  }, [pathname, searchParams])
  const activeConversionId = createdConversion?.id ?? queryConversionId
  const conversionResponse = useConversion(activeConversionId ?? "")
  const selectedSavedConfigResponse = useSavedConversionConfig(
    selectedSavedConfigId
  )

  const assets = React.useMemo(
    () => assetsResponse.data ?? [],
    [assetsResponse.data]
  )
  const selectedAssets = React.useMemo(
    () => assets.filter((asset) => assetIdSet.has(asset.id)),
    [assetIdSet, assets]
  )
  const selectedSourceAsset =
    selectedAssets.find((asset) => asset.id === sourceAssetId) ??
    selectedAssets[0] ??
    null
  const selectedSavedConfig = selectedSavedConfigResponse.data ?? null
  const savedConfigs = React.useMemo(
    () => savedConfigsResponse.data ?? [],
    [savedConfigsResponse.data]
  )
  const selectedConfigSummary = React.useMemo(
    () =>
      savedConfigs.find((config) => config.id === selectedSavedConfigId) ??
      null,
    [savedConfigs, selectedSavedConfigId]
  )
  const selectedSavedConfigExists = React.useMemo(
    () => savedConfigs.some((config) => config.id === selectedSavedConfigId),
    [savedConfigs, selectedSavedConfigId]
  )
  const inspectionTopicNames = React.useMemo(
    () => Object.keys(inspectionResponse?.inspection.topics ?? {}),
    [inspectionResponse?.inspection.topics]
  )
  const effectiveSelectedTopics = React.useMemo(
    () =>
      specForm.selectedTopics.length > 0
        ? normalizeTopicList(specForm.selectedTopics)
        : normalizeTopicList(inspectionTopicNames),
    [inspectionTopicNames, specForm.selectedTopics]
  )
  const effectiveTriggerTopic = React.useMemo(() => {
    const normalizedTrigger = specForm.triggerTopic.trim()
    if (
      normalizedTrigger &&
      effectiveSelectedTopics.includes(normalizedTrigger)
    ) {
      return normalizedTrigger
    }

    return effectiveSelectedTopics[0] ?? inspectionTopicNames[0] ?? ""
  }, [effectiveSelectedTopics, inspectionTopicNames, specForm.triggerTopic])
  const specParse = React.useMemo(() => parseJsonObject(specText), [specText])
  const topicHintsParse = React.useMemo(
    () => parseOptionalTopicTypeHints(inspectionForm.topicTypeHints),
    [inspectionForm.topicTypeHints]
  )
  const topicTypeHints = React.useMemo(
    () => topicHintsParse.value ?? ({} as Record<string, string>),
    [topicHintsParse.value]
  )
  const currentSpecSummary = React.useMemo(
    () => summarizeConversionSpec(specParse.value ?? null),
    [specParse.value]
  )
  const selectedConfigSpecSummary = React.useMemo(
    () =>
      summarizeConversionSpec(
        selectedSavedConfig ? resolveSavedConfigSpec(selectedSavedConfig) : null
      ),
    [selectedSavedConfig]
  )
  const unindexedAssets = React.useMemo(
    () => selectedAssets.filter((asset) => asset.indexing_status !== "indexed"),
    [selectedAssets]
  )
  const missingAssetCount = Math.max(assetIds.length - selectedAssets.length, 0)
  const activeConversion = createdConversion ?? conversionResponse.data ?? null
  const outputContract = React.useMemo(
    () =>
      normalizeOutputContractCapabilities(
        capabilitiesResponse.data?.output_contract
      ),
    [capabilitiesResponse.data?.output_contract]
  )
  const authoringRepresentationPolicy =
    previewResponse?.representation_policy ??
    draftResponse?.representation_policy ??
    inspectionResponse?.representation_policy ??
    null
  const statusRepresentationPolicy =
    activeConversion?.representation_policy ??
    activeConversion?.job.representation_policy ??
    null
  const isPendingConversionRoute =
    Boolean(queryConversionId) &&
    !createdConversion &&
    conversionResponse.isLoading
  const isStatusMode = Boolean(activeConversion)

  const updateRouteQuery = React.useCallback(
    ({
      conversionId,
      savedConfigId,
      sourceId,
      targetMode = mode,
    }: {
      conversionId?: string | null
      savedConfigId?: string | null
      sourceId?: string | null
      targetMode?: ConversionWorkspaceMode
    }) => {
      const nextHref =
        targetMode === "create"
          ? buildConversionCreateHref({
              assetIds,
              from: searchParams.get("from"),
              sourceAssetId: sourceId,
            })
          : buildConversionUseHref({
              assetIds,
              conversionId,
              from: searchParams.get("from"),
              savedConfigId,
              sourceAssetId: sourceId,
            })

      React.startTransition(() => {
        router.replace(nextHref, { scroll: false })
      })
    },
    [assetIds, mode, router, searchParams]
  )

  React.useEffect(() => {
    if (!isUseMode) {
      return
    }

    if (savedConfigsResponse.data === undefined) {
      return
    }

    if (savedConfigs.length === 0) {
      updateRouteQuery({
        sourceId: sourceAssetId || null,
        targetMode: "create",
      })
      return
    }

    if (selectedSavedConfigExists) {
      return
    }

    const firstSavedConfigId = savedConfigs[0]?.id
    if (!firstSavedConfigId) {
      return
    }

    setSelectedSavedConfigId(firstSavedConfigId)
    updateRouteQuery({
      savedConfigId: firstSavedConfigId,
      sourceId: sourceAssetId || null,
      targetMode: "use",
    })
  }, [
    isUseMode,
    savedConfigs,
    savedConfigsResponse.data,
    selectedSavedConfigExists,
    sourceAssetId,
    updateRouteQuery,
  ])

  React.useEffect(() => {
    if (isCreateMode || !selectedSavedConfig) {
      return
    }

    const resolvedSpec = resolveSavedConfigSpec(selectedSavedConfig)
    if (resolvedSpec) {
      setSpecText(stringifyJson(resolvedSpec))
      setPreviewResponse(null)
    }
  }, [isCreateMode, selectedSavedConfig])

  React.useEffect(() => {
    if (!draftResponse) {
      return
    }

    setSpecText(stringifyJson(draftResponse.draft.spec))
    setPreviewResponse(
      draftResponse.draft.preview
        ? {
            asset_id: draftResponse.asset_id,
            preview: draftResponse.draft.preview,
            request: {
              asset_id: draftResponse.asset_id,
              sample_n: Number(specForm.previewRows),
              spec: draftResponse.draft.spec,
              topic_type_hints: topicTypeHints,
            },
          }
        : null
    )
  }, [draftResponse, specForm.previewRows, topicTypeHints])

  React.useEffect(() => {
    if (!selectedSourceAsset) {
      return
    }

    setSourceAssetId(selectedSourceAsset.id)
  }, [selectedSourceAsset])

  React.useEffect(() => {
    if (!activeConversion) {
      return
    }

    if (
      !isWorkflowActiveStatus(activeConversion.status) &&
      !isWorkflowActiveStatus(activeConversion.job.status)
    ) {
      return
    }

    const intervalId = window.setInterval(() => {
      void (async () => {
        try {
          if (activeConversion.id) {
            await conversionResponse.mutate()
            await Promise.all([
              revalidateConversionDetail(activeConversion.id),
              revalidateConversions(),
              revalidateJobs(),
              revalidateOutputs(),
            ])
          }
        } catch {
          // Keep the last known status visible if polling fails briefly.
        }
      })()
    }, 1500)

    return () => window.clearInterval(intervalId)
  }, [
    activeConversion,
    conversionResponse,
    revalidateConversionDetail,
    revalidateConversions,
    revalidateJobs,
    revalidateOutputs,
  ])

  function resetForAnotherConversion() {
    setCreatedConversion(null)
    setRequestMessage(null)
    updateRouteQuery({
      savedConfigId: selectedSavedConfigId || null,
      sourceId: sourceAssetId || null,
    })
  }

  function loadSourceAsset(assetId: string) {
    setSourceAssetId(assetId)
    setInspectionResponse(null)
    setDraftResponse(null)
    setPreviewResponse(null)
    setSpecText("")
    setCreateStep("source")
    updateRouteQuery({
      savedConfigId: selectedSavedConfigId || null,
      sourceId: assetId,
    })
  }

  function handleSpecTextChange(nextText: string) {
    setSpecText(nextText)

    if (isCreateMode) {
      setPreviewResponse(null)
    }
  }

  function selectSavedConfig(configId: string) {
    setSelectedSavedConfigId(configId)
    updateRouteQuery({
      savedConfigId: configId,
      sourceId: sourceAssetId || null,
    })
  }

  function getNextTriggerTopic(
    nextTopics: string[],
    currentTrigger: string | null | undefined
  ) {
    const normalizedTrigger = currentTrigger?.trim() ?? ""
    if (normalizedTrigger && nextTopics.includes(normalizedTrigger)) {
      return normalizedTrigger
    }

    return nextTopics[0] ?? ""
  }

  function toggleSelectedTopic(topic: string) {
    setSpecForm((current) => {
      const baseTopics =
        current.selectedTopics.length > 0
          ? current.selectedTopics
          : inspectionTopicNames
      const nextTopics = baseTopics.includes(topic)
        ? baseTopics.filter((item) => item !== topic)
        : normalizeTopicList([...baseTopics, topic])

      return {
        ...current,
        selectedTopics: nextTopics,
        triggerTopic: getNextTriggerTopic(nextTopics, current.triggerTopic),
      }
    })
  }

  function selectTriggerTopic(topic: string) {
    setSpecForm((current) => {
      const baseTopics =
        current.selectedTopics.length > 0
          ? current.selectedTopics
          : inspectionTopicNames
      const nextTopics = baseTopics.includes(topic)
        ? baseTopics
        : normalizeTopicList([...baseTopics, topic])

      return {
        ...current,
        selectedTopics: nextTopics,
        triggerTopic: topic,
      }
    })
  }

  function clearTriggerTopic(topic: string) {
    setSpecForm((current) => {
      const baseTopics =
        current.selectedTopics.length > 0
          ? current.selectedTopics
          : inspectionTopicNames
      const nextTrigger =
        baseTopics.find((item) => item !== topic) ?? baseTopics[0] ?? ""

      return {
        ...current,
        triggerTopic: nextTrigger,
      }
    })
  }

  async function runInspection() {
    if (!selectedSourceAsset) {
      return
    }

    if (topicHintsParse.error) {
      setRequestMessage({
        description: topicHintsParse.error,
        title: "Topic type hints must be valid JSON",
        tone: "error",
      })
      return
    }

    const payload: ConversionInspectionRequest = {
      asset_id: selectedSourceAsset.id,
      max_depth: Number(inspectionForm.maxDepth),
      max_sequence_items: Number(inspectionForm.maxSequenceItems),
      on_failure: inspectionForm.onFailure,
      sample_n: Number(inspectionForm.sampleN),
      topics: [],
      topic_type_hints: topicTypeHints,
    }

    setIsInspecting(true)
    setRequestMessage(null)

    try {
      const result = await inspectConversion(payload)
      setInspectionResponse(result)
      setDraftResponse(null)
      setPreviewResponse(null)
      setSpecText("")
      setSpecForm((current) => ({
        ...current,
        selectedTopics: [],
        triggerTopic: "",
      }))
      toast.success("Inspection complete")
    } catch (error) {
      const message = getErrorMessage(error)
      setRequestMessage({
        description: message,
        title: "Could not inspect the asset",
        tone: "error",
      })
      toast.error("Inspection failed", {
        description: message,
      })
    } finally {
      setIsInspecting(false)
    }
  }

  async function runDraft() {
    if (!selectedSourceAsset) {
      return
    }

    if (topicHintsParse.error) {
      setRequestMessage({
        description: topicHintsParse.error,
        title: "Topic type hints must be valid JSON",
        tone: "error",
      })
      return
    }

    const selectedTopics = effectiveSelectedTopics
    if (selectedTopics.length === 0) {
      setRequestMessage({
        description: "Inspect at least one topic before drafting.",
        title: "No topics selected",
        tone: "error",
      })
      return
    }

    const triggerTopic = effectiveTriggerTopic || selectedTopics[0] || null
    const payload: ConversionDraftRequest = {
      asset_id: selectedSourceAsset.id,
      max_depth: Number(inspectionForm.maxDepth),
      max_sequence_items: Number(inspectionForm.maxSequenceItems),
      on_failure: inspectionForm.onFailure,
      sample_n: Number(inspectionForm.sampleN),
      topics: selectedTopics,
      topic_type_hints: topicTypeHints,
      draft_request: {
        include_preview: specForm.includePreview,
        join_topics: selectedTopics.filter((topic) => topic !== triggerTopic),
        label_feature: specForm.labelFeature.trim() || null,
        max_features_per_topic: Number(specForm.maxFeaturesPerTopic),
        output_compression: specForm.outputCompression,
        output_format: specForm.outputFormat,
        preview_rows: Number(specForm.previewRows),
        schema_name: specForm.schemaName.trim() || "draft_conversion",
        schema_version: Number(specForm.schemaVersion),
        selected_topics: selectedTopics,
        trigger_topic: triggerTopic,
      },
    }

    setIsDrafting(true)
    setRequestMessage(null)

    try {
      const result = await draftConversion(payload)
      setDraftResponse(result)
      setSpecText(stringifyJson(result.draft.spec))
      if (result.draft.preview) {
        setPreviewResponse({
          asset_id: result.asset_id,
          preview: result.draft.preview,
          request: {
            asset_id: result.asset_id,
            sample_n: Number(specForm.previewRows),
            spec: result.draft.spec,
            topic_type_hints: topicTypeHints,
          },
        })
      } else {
        setPreviewResponse(null)
      }
      toast.success("Draft generated")
    } catch (error) {
      const message = getErrorMessage(error)
      setRequestMessage({
        description: message,
        title: "Could not draft a spec",
        tone: "error",
      })
      toast.error("Draft generation failed", {
        description: message,
      })
    } finally {
      setIsDrafting(false)
    }
  }

  async function runPreview() {
    if (!selectedSourceAsset) {
      return
    }

    const parsedSpec = parseJsonObject(specText)
    if (parsedSpec.error || !parsedSpec.value) {
      setRequestMessage({
        description: parsedSpec.error ?? "Enter a valid conversion spec first.",
        title: "Spec JSON is invalid",
        tone: "error",
      })
      return
    }

    if (topicHintsParse.error) {
      setRequestMessage({
        description: topicHintsParse.error,
        title: "Topic type hints must be valid JSON",
        tone: "error",
      })
      return
    }

    const payload: ConversionPreviewRequest = {
      asset_id: selectedSourceAsset.id,
      sample_n: Number(specForm.previewRows),
      spec: parsedSpec.value,
      topic_type_hints: topicTypeHints,
    }

    setIsPreviewing(true)
    setRequestMessage(null)

    try {
      const result = await previewConversion(payload)
      setPreviewResponse(result)
      toast.success("Preview generated")
    } catch (error) {
      const message = getErrorMessage(error)
      setRequestMessage({
        description: message,
        title: "Could not preview the spec",
        tone: "error",
      })
      toast.error("Preview failed", {
        description: message,
      })
    } finally {
      setIsPreviewing(false)
    }
  }

  async function runSavedConfigConversion() {
    if (!selectedSavedConfigId || !selectedSavedConfig) {
      return
    }

    if (unindexedAssets.length > 0) {
      setRequestMessage({
        description:
          "Index the selected assets before executing the saved config.",
        title: "Assets are not indexed yet",
        tone: "error",
      })
      return
    }

    setIsRunningSavedConfig(true)
    setRequestMessage(null)

    try {
      const payload: ConversionCreateRequest = {
        asset_ids: selectedAssets.map((asset) => asset.id),
        saved_config_id: selectedSavedConfigId,
      }

      const result = await submitConversion(payload, selectedAssets)
      if (result.conversion) {
        setCreatedConversion(result.conversion)
        updateRouteQuery({
          conversionId: result.conversion.id,
          savedConfigId: selectedSavedConfigId,
          sourceId: sourceAssetId || null,
        })
      }

      if (result.notice) {
        setRequestMessage({
          description: result.notice.description,
          title: result.notice.title,
          tone: "error",
        })
        toast.error("Conversion failed", {
          description: result.notice.description,
        })
      }
    } finally {
      setIsRunningSavedConfig(false)
    }
  }

  async function submitConfigDialog() {
    const parsedSpec = parseJsonObject(specText)
    if (parsedSpec.error || !parsedSpec.value) {
      setRequestMessage({
        description: parsedSpec.error ?? "Enter a valid conversion spec first.",
        title: "Spec JSON is invalid",
        tone: "error",
      })
      return
    }

    if (!configDialogName.trim()) {
      setRequestMessage({
        description: "Give the saved config a name before saving it.",
        title: "Name is required",
        tone: "error",
      })
      return
    }

    const metadata = buildWorkspaceMetadata(assetIds, sourceAssetId || null)
    setIsSavingConfig(true)
    setRequestMessage(null)

    try {
      if (configDialogMode === "update" && selectedSavedConfigId) {
        const result = await updateConversionConfig(selectedSavedConfigId, {
          description: configDialogDescription.trim() || null,
          metadata,
          name: configDialogName.trim(),
          spec: parsedSpec.value,
        })
        setSelectedSavedConfigId(result.id)
        setSpecText(
          stringifyJson(resolveSavedConfigSpec(result) ?? parsedSpec.value)
        )
        await Promise.all([
          revalidateSavedConfigs(),
          revalidateSavedConfigDetail(result.id),
        ])
        updateRouteQuery({
          savedConfigId: result.id,
          sourceId: sourceAssetId || null,
        })
        toast.success("Saved config updated")
      } else if (configDialogMode === "duplicate" && selectedSavedConfigId) {
        const result = await duplicateConversionConfig(selectedSavedConfigId, {
          description: configDialogDescription.trim() || null,
          metadata,
          name: configDialogName.trim(),
        })
        setSelectedSavedConfigId(result.id)
        setSpecText(
          stringifyJson(resolveSavedConfigSpec(result) ?? parsedSpec.value)
        )
        await Promise.all([
          revalidateSavedConfigs(),
          revalidateSavedConfigDetail(result.id),
        ])
        updateRouteQuery({
          savedConfigId: result.id,
          sourceId: sourceAssetId || null,
        })
        toast.success("Saved config duplicated")
      } else {
        const result = await createConversionConfig({
          description: configDialogDescription.trim() || null,
          metadata,
          name: configDialogName.trim(),
          spec: parsedSpec.value,
        })
        await Promise.all([
          revalidateSavedConfigs(),
          revalidateSavedConfigDetail(result.id),
        ])
        const nextHref = buildConversionUseHref({
          assetIds,
          from: searchParams.get("from"),
          savedConfigId: result.id,
          sourceAssetId: sourceAssetId || null,
        })
        setSelectedSavedConfigId(result.id)
        setSpecText(
          stringifyJson(resolveSavedConfigSpec(result) ?? parsedSpec.value)
        )
        React.startTransition(() => {
          router.push(nextHref, { scroll: false })
        })
        toast.success("Saved config created")
      }
    } catch (error) {
      const message = getErrorMessage(error)
      setRequestMessage({
        description: message,
        title: "Could not save the config",
        tone: "error",
      })
      toast.error("Save failed", {
        description: message,
      })
    } finally {
      setIsSavingConfig(false)
      setConfigDialogMode(null)
    }
  }

  function openCreateDialog() {
    const currentName = selectedSavedConfig?.name ?? "New authoring config"
    const currentDescription = selectedSavedConfig?.description ?? ""
    setConfigDialogMode("create")
    setConfigDialogName(currentName)
    setConfigDialogDescription(currentDescription)
  }

  function openUpdateDialog() {
    if (!selectedSavedConfig) {
      return
    }

    setConfigDialogMode("update")
    setConfigDialogName(selectedSavedConfig.name)
    setConfigDialogDescription(selectedSavedConfig.description ?? "")
  }

  function openDuplicateDialog() {
    if (!selectedSavedConfig) {
      return
    }

    setConfigDialogMode("duplicate")
    setConfigDialogName(`Copy of ${selectedSavedConfig.name}`)
    setConfigDialogDescription(selectedSavedConfig.description ?? "")
  }

  if (assetsResponse.isLoading && !assetsResponse.data && !isStatusMode) {
    return (
      <div className="space-y-6">
        <div className="h-9 w-24 rounded bg-muted" />
        <div className="space-y-3">
          <div className="h-8 w-48 rounded bg-muted" />
          <div className="h-5 w-full max-w-3xl rounded bg-muted" />
        </div>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)]">
          <div className="space-y-4">
            <div className="h-40 rounded-xl bg-muted" />
            <div className="h-80 rounded-xl bg-muted" />
            <div className="h-96 rounded-xl bg-muted" />
          </div>
          <div className="space-y-4">
            <div className="h-56 rounded-xl bg-muted" />
            <div className="h-56 rounded-xl bg-muted" />
          </div>
        </div>
      </div>
    )
  }

  if (isPendingConversionRoute) {
    return (
      <div className="space-y-6">
        <div className="h-9 w-24 rounded bg-muted" />
        <div className="h-72 rounded-xl bg-muted" />
      </div>
    )
  }

  if (queryConversionId && conversionResponse.error) {
    const isMissingConversion =
      conversionResponse.error instanceof BackendApiError &&
      conversionResponse.error.status === 404

    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTitle>
            {isMissingConversion
              ? "Conversion not found"
              : "Could not load conversion"}
          </AlertTitle>
          <AlertDescription>
            {getErrorMessage(conversionResponse.error)}
          </AlertDescription>
        </Alert>
        {!isMissingConversion ? (
          <div>
            <Button
              onClick={() => void conversionResponse.mutate()}
              type="button"
              variant="outline"
            >
              Try again
            </Button>
          </div>
        ) : null}
      </div>
    )
  }

  if (assetsResponse.error && !isStatusMode) {
    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTitle>Could not load assets</AlertTitle>
          <AlertDescription>
            {getErrorMessage(assetsResponse.error)}
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!isStatusMode && assetIds.length === 0) {
    return (
      <div className="space-y-6">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <EmptyState
          action={
            <Button asChild variant="outline">
              <Link href="/inventory">Go to inventory</Link>
            </Button>
          }
          description="Open this page from inventory or asset detail so we know which assets to inspect and convert."
          title="No assets selected"
        />
      </div>
    )
  }

  if (!isStatusMode && missingAssetCount > 0) {
    return (
      <div className="space-y-4">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <Alert variant="destructive">
          <TriangleAlert className="size-4" />
          <AlertTitle>Selected assets are no longer available</AlertTitle>
          <AlertDescription>
            {missingAssetCount} selected asset
            {missingAssetCount === 1 ? "" : "s"} could not be resolved from the
            current inventory. Go back and choose a fresh selection.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  if (isStatusMode && activeConversion) {
    return (
      <div className="space-y-6">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>
        <section className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold tracking-tight">
                Conversion status
              </h1>
              <p className="max-w-3xl text-sm text-muted-foreground">
                The final conversion is now running. Stay on this page to watch
                the backend-managed status update.
              </p>
            </div>
          </div>
        </section>

        <ConversionStatusCard
          activeConversion={activeConversion}
          currentHref={currentHref}
          isRefreshing={isSubmitting}
          onNewConversion={resetForAnotherConversion}
        />
      </div>
    )
  }

  const selectedConfigSpec = selectedSavedConfig
    ? resolveSavedConfigSpec(selectedSavedConfig)
    : null
  const selectedConfigPreview = selectedSavedConfig?.latest_preview ?? null
  const inspectionWarnings = inspectionResponse?.inspection.warnings ?? []
  const draftCompleteIndicator = draftResponse ? (
    <span className="inline-flex items-center gap-1 text-sm font-medium text-emerald-600">
      <CheckCircle2 className="size-4" />
      Draft complete
    </span>
  ) : null

  if (isCreateMode) {
    return (
      <div className="space-y-6">
        <Button asChild size="sm" variant="ghost">
          <Link href={returnHref}>
            <ArrowLeft className="size-4" />
            Back
          </Link>
        </Button>

        <section className="space-y-2">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
                <Sparkles className="size-5" />
                Create conversion config
              </h1>
            </div>
            <CreateWizardBreadcrumb
              currentStep={createStep}
              onStepChange={(step) => setCreateStep(step)}
            />
          </div>
        </section>

        {requestMessage ? (
          <Alert
            variant={
              requestMessage.tone === "error" ? "destructive" : "default"
            }
          >
            <TriangleAlert className="size-4" />
            <AlertTitle>{requestMessage.title}</AlertTitle>
            {requestMessage.description ? (
              <AlertDescription>{requestMessage.description}</AlertDescription>
            ) : null}
          </Alert>
        ) : null}

        {unindexedAssets.length > 0 ? (
          <Alert variant="destructive">
            <TriangleAlert className="size-4" />
            <AlertTitle>Index assets before converting</AlertTitle>
            <AlertDescription>
              {unindexedAssets
                .slice(0, 3)
                .map((asset) => asset.file_name)
                .join(", ")}
              {unindexedAssets.length > 3
                ? ` and ${unindexedAssets.length - 3} more`
                : ""}{" "}
              must finish indexing before the conversion can run.
            </AlertDescription>
          </Alert>
        ) : null}

        {createStep === "source" ? (
          <Card>
            <CardHeader>
              <CardTitle>Source asset</CardTitle>
              <CardDescription>
                Pick the asset the backend should inspect first.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="source-asset">Source asset</Label>
                <NativeSelect
                  id="source-asset"
                  onChange={(event) => loadSourceAsset(event.target.value)}
                  value={selectedSourceAsset?.id ?? ""}
                >
                  {selectedAssets.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.file_name}
                    </option>
                  ))}
                </NativeSelect>
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-1">
                  <p className="text-xs tracking-wide text-muted-foreground uppercase">
                    File type
                  </p>
                  <p className="text-sm font-medium">
                    {selectedSourceAsset?.file_type ?? "Not available"}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs tracking-wide text-muted-foreground uppercase">
                    Size
                  </p>
                  <p className="text-sm font-medium">
                    {selectedSourceAsset
                      ? formatFileSize(selectedSourceAsset.file_size)
                      : "Not available"}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs tracking-wide text-muted-foreground uppercase">
                    Registered
                  </p>
                  <p className="text-sm font-medium">
                    {selectedSourceAsset
                      ? formatDateTime(selectedSourceAsset.registered_time)
                      : "Not available"}
                  </p>
                </div>
              </div>

              <div className="flex justify-end">
                <Button
                  disabled={!selectedSourceAsset}
                  onClick={() => setCreateStep("inspect")}
                  type="button"
                >
                  Continue to inspect
                  <ArrowRight className="size-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {createStep === "inspect" ? (
          <Card>
            <CardHeader>
              <CardTitle>Inspect</CardTitle>
              <CardDescription>
                Inspect {selectedSourceAsset?.file_name ?? "the selected asset"}{" "}
                and surface topic candidates.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <Accordion className="space-y-3" type="multiple">
                <AccordionItem value="inspect-settings">
                  <AccordionTrigger>
                    <span className="text-sm font-medium text-foreground">
                      Inspect Settings
                    </span>
                  </AccordionTrigger>
                  <AccordionContent className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                      <div className="space-y-2">
                        <Label htmlFor="sample-n">Sample count</Label>
                        <Input
                          id="sample-n"
                          min="1"
                          onChange={(event) =>
                            setInspectionForm((current) => ({
                              ...current,
                              sampleN: event.target.value,
                            }))
                          }
                          type="number"
                          value={inspectionForm.sampleN}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="max-depth">Max depth</Label>
                        <Input
                          id="max-depth"
                          min="0"
                          onChange={(event) =>
                            setInspectionForm((current) => ({
                              ...current,
                              maxDepth: event.target.value,
                            }))
                          }
                          type="number"
                          value={inspectionForm.maxDepth}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="max-sequence-items">
                          Sequence items
                        </Label>
                        <Input
                          id="max-sequence-items"
                          min="1"
                          onChange={(event) =>
                            setInspectionForm((current) => ({
                              ...current,
                              maxSequenceItems: event.target.value,
                            }))
                          }
                          type="number"
                          value={inspectionForm.maxSequenceItems}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="on-failure">Decode failure</Label>
                        <NativeSelect
                          id="on-failure"
                          onChange={(event) =>
                            setInspectionForm((current) => ({
                              ...current,
                              onFailure: event.target
                                .value as DecodeFailurePolicy,
                            }))
                          }
                          value={inspectionForm.onFailure}
                        >
                          <option value="skip">Skip</option>
                          <option value="warn">Warn</option>
                          <option value="fail">Fail</option>
                        </NativeSelect>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="topic-type-hints">
                  <AccordionTrigger>
                    <span className="flex min-w-0 flex-1 items-center justify-between gap-3">
                      <span className="text-sm font-medium text-foreground">
                        Topic type hints
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {getTopicHintCount(inspectionForm.topicTypeHints) ?? 0}{" "}
                        hints
                      </span>
                    </span>
                  </AccordionTrigger>
                  <AccordionContent className="space-y-2">
                    <Textarea
                      id="topic-type-hints"
                      onChange={(event) =>
                        setInspectionForm((current) => ({
                          ...current,
                          topicTypeHints: event.target.value,
                        }))
                      }
                      placeholder='{"\/camera/front/image_raw": "sensor_msgs/msg/Image"}'
                      value={inspectionForm.topicTypeHints}
                    />
                    {topicHintsParse.error ? (
                      <p className="text-sm text-destructive">
                        {topicHintsParse.error}
                      </p>
                    ) : null}
                  </AccordionContent>
                </AccordionItem>
              </Accordion>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  disabled={isInspecting || !selectedSourceAsset}
                  onClick={runInspection}
                  type="button"
                >
                  {isInspecting ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <SearchIconFallback />
                  )}
                  {isInspecting ? "Inspecting..." : "Inspect asset"}
                </Button>
              </div>

              {inspectionWarnings.length > 0 ? (
                <Alert>
                  <TriangleAlert className="size-4" />
                  <AlertTitle>Inspection warnings</AlertTitle>
                  <AlertDescription>
                    <ul className="mt-2 list-disc space-y-1 pl-5">
                      {inspectionWarnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              ) : null}

              {inspectionResponse ? (
                <div className="space-y-3">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="space-y-1">
                      <p className="text-xs tracking-wide text-muted-foreground uppercase">
                        ROS version
                      </p>
                      <p className="text-sm font-medium">
                        {inspectionResponse.inspection.ros_version ?? "Unknown"}
                      </p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs tracking-wide text-muted-foreground uppercase">
                        Sample count
                      </p>
                      <p className="text-sm font-medium">
                        {inspectionResponse.inspection.sample_n}
                      </p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs tracking-wide text-muted-foreground uppercase">
                        Topics found
                      </p>
                      <p className="text-sm font-medium">
                        {inspectionTopicNames.length}
                      </p>
                    </div>
                  </div>

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Topic</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Samples</TableHead>
                        <TableHead>Candidates</TableHead>
                        <TableHead>Top fields</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {inspectionTopicNames.map((topicName) => {
                        const topic =
                          inspectionResponse.inspection.topics[topicName]
                        const summary = summarizeInspectionTopic(topic)

                        return (
                          <TableRow key={topicName}>
                            <TableCell className="font-medium">
                              {topicName}
                            </TableCell>
                            <TableCell>
                              {topic.message_type ?? "Unknown"}
                            </TableCell>
                            <TableCell>{summary.sampleCount}</TableCell>
                            <TableCell>{summary.candidateCount}</TableCell>
                            <TableCell className="max-w-[24rem] whitespace-normal">
                              {summary.firstCandidatePaths.length > 0
                                ? summary.firstCandidatePaths.join(", ")
                                : "None"}
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <EmptyState
                  variant="card"
                  description="Run inspection to see topic candidates and field summaries here."
                  title="No inspection yet"
                />
              )}

              <div className="flex justify-between gap-2">
                <Button
                  onClick={() => setCreateStep("source")}
                  type="button"
                  variant="outline"
                >
                  <ArrowLeft className="size-4" />
                  Back
                </Button>
                <Button
                  disabled={!inspectionResponse}
                  onClick={() => setCreateStep("draft")}
                  type="button"
                >
                  Continue to draft
                  <ArrowRight className="size-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {createStep === "draft" ? (
          <Card>
            <CardHeader>
              <CardTitle>Draft</CardTitle>
              <CardDescription>
                Choose the topics and draft settings the backend should use.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <div className="space-y-2">
                  <Label htmlFor="schema-name">Schema name</Label>
                  <Input
                    id="schema-name"
                    onChange={(event) =>
                      setSpecForm((current) => ({
                        ...current,
                        schemaName: event.target.value,
                      }))
                    }
                    value={specForm.schemaName}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="schema-version">Schema version</Label>
                  <Input
                    id="schema-version"
                    min="1"
                    onChange={(event) =>
                      setSpecForm((current) => ({
                        ...current,
                        schemaVersion: event.target.value,
                      }))
                    }
                    type="number"
                    value={specForm.schemaVersion}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="output-format">Output format</Label>
                  <NativeSelect
                    id="output-format"
                    onChange={(event) =>
                      setSpecForm((current) => ({
                        ...current,
                        outputFormat: event.target.value as ConversionFormat,
                      }))
                    }
                    value={specForm.outputFormat}
                  >
                    <option value="tfrecord">TFRecord</option>
                    <option value="parquet">Parquet</option>
                  </NativeSelect>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="output-compression">Compression</Label>
                  <NativeSelect
                    id="output-compression"
                    onChange={(event) =>
                      setSpecForm((current) => ({
                        ...current,
                        outputCompression: event.target.value,
                      }))
                    }
                    value={specForm.outputCompression}
                  >
                    {specForm.outputFormat === "parquet"
                      ? ["none", "snappy", "gzip", "brotli", "lz4", "zstd"].map(
                          (compression) => (
                            <option key={compression} value={compression}>
                              {formatSentenceCase(compression)}
                            </option>
                          )
                        )
                      : ["none", "gzip"].map((compression) => (
                          <option key={compression} value={compression}>
                            {formatSentenceCase(compression)}
                          </option>
                        ))}
                  </NativeSelect>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max-features-per-topic">
                    Max features/topic
                  </Label>
                  <Input
                    id="max-features-per-topic"
                    min="1"
                    onChange={(event) =>
                      setSpecForm((current) => ({
                        ...current,
                        maxFeaturesPerTopic: event.target.value,
                      }))
                    }
                    type="number"
                    value={specForm.maxFeaturesPerTopic}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="preview-rows">Preview rows</Label>
                  <Input
                    id="preview-rows"
                    min="1"
                    onChange={(event) =>
                      setSpecForm((current) => ({
                        ...current,
                        previewRows: event.target.value,
                      }))
                    }
                    type="number"
                    value={specForm.previewRows}
                  />
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
                <div className="space-y-1">
                  <Label htmlFor="label-feature">Label feature</Label>
                  <Input
                    id="label-feature"
                    onChange={(event) =>
                      setSpecForm((current) => ({
                        ...current,
                        labelFeature: event.target.value,
                      }))
                    }
                    placeholder="Optional"
                    value={specForm.labelFeature}
                  />
                </div>
                <div className="flex items-center justify-between gap-4 lg:self-center">
                  <Label
                    className="text-sm font-medium text-foreground"
                    htmlFor="include-preview"
                  >
                    Include preview
                  </Label>
                  <Switch
                    checked={specForm.includePreview}
                    id="include-preview"
                    onCheckedChange={(checked) =>
                      setSpecForm((current) => ({
                        ...current,
                        includePreview: checked,
                      }))
                    }
                  />
                </div>
              </div>

              {inspectionResponse ? (
                <div className="space-y-3">
                  <div className="space-y-1">
                    <p className="text-xs tracking-wide text-muted-foreground uppercase">
                      Selected topics
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Use picks the topics that will drive the draft. Trigger
                      marks the one topic that should anchor it.
                    </p>
                  </div>

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">Use</TableHead>
                        <TableHead className="w-16">Trigger</TableHead>
                        <TableHead>Topic</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Samples</TableHead>
                        <TableHead>Fields</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {inspectionTopicNames.map((topicName) => {
                        const topic =
                          inspectionResponse.inspection.topics[topicName]
                        const summary = summarizeInspectionTopic(topic)
                        const checked =
                          effectiveSelectedTopics.includes(topicName)
                        const isTrigger = effectiveTriggerTopic === topicName

                        return (
                          <TableRow key={topicName}>
                            <TableCell>
                              <Checkbox
                                checked={checked}
                                onCheckedChange={() =>
                                  toggleSelectedTopic(topicName)
                                }
                              />
                            </TableCell>
                            <TableCell>
                              <Checkbox
                                checked={isTrigger}
                                onCheckedChange={(nextChecked) => {
                                  if (nextChecked) {
                                    selectTriggerTopic(topicName)
                                  } else {
                                    clearTriggerTopic(topicName)
                                  }
                                }}
                              />
                            </TableCell>
                            <TableCell className="font-medium">
                              {topicName}
                            </TableCell>
                            <TableCell>
                              {topic.message_type ?? "Unknown"}
                            </TableCell>
                            <TableCell>{summary.sampleCount}</TableCell>
                            <TableCell className="max-w-[24rem] whitespace-normal">
                              {summary.firstCandidatePaths.length > 0
                                ? summary.firstCandidatePaths.join(", ")
                                : "None"}
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <EmptyState
                  variant="card"
                  description="Inspect the source asset first so the backend can suggest topics for the draft."
                  title="Draft needs inspection"
                />
              )}

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  disabled={
                    isDrafting ||
                    !selectedSourceAsset ||
                    effectiveSelectedTopics.length === 0
                  }
                  onClick={runDraft}
                  type="button"
                >
                  {isDrafting ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <FileJson2 className="size-4" />
                  )}
                  {isDrafting ? "Drafting..." : "Draft spec"}
                </Button>
                {draftCompleteIndicator}
              </div>

              <div className="flex justify-between gap-2">
                <Button
                  onClick={() => setCreateStep("inspect")}
                  type="button"
                  variant="outline"
                >
                  <ArrowLeft className="size-4" />
                  Back
                </Button>
                <Button
                  disabled={!draftResponse}
                  onClick={() => setCreateStep("spec")}
                  type="button"
                >
                  Continue to spec editor
                  <ArrowRight className="size-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {createStep === "spec" ? (
          <Card>
            <CardHeader>
              <CardTitle>Spec editor</CardTitle>
              <CardDescription>
                Keep the contract visible. The backend still validates the real
                shape.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-xs tracking-wide text-muted-foreground uppercase">
                    Summary
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {currentSpecSummary.schemaName ?? "No spec loaded"}{" "}
                    {currentSpecSummary.schemaVersion !== null
                      ? `v${currentSpecSummary.schemaVersion}`
                      : ""}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    disabled={!draftResponse}
                    onClick={() => {
                      if (!draftResponse) {
                        return
                      }

                      setSpecText(stringifyJson(draftResponse.draft.spec))
                      setPreviewResponse(
                        draftResponse.draft.preview
                          ? {
                              asset_id: draftResponse.asset_id,
                              preview: draftResponse.draft.preview,
                              request: {
                                asset_id: draftResponse.asset_id,
                                sample_n: Number(specForm.previewRows),
                                spec: draftResponse.draft.spec,
                                topic_type_hints: topicTypeHints,
                              },
                            }
                          : null
                      )
                    }}
                    type="button"
                    variant="outline"
                  >
                    Load draft
                  </Button>
                  <Button
                    disabled={specParse.error !== null}
                    onClick={() => {
                      if (!specParse.value) {
                        return
                      }

                      setSpecText(stringifyJson(specParse.value))
                    }}
                    type="button"
                    variant="outline"
                  >
                    Format JSON
                  </Button>
                </div>
              </div>

              <Textarea
                className="min-h-[420px] font-mono text-sm"
                onChange={(event) => handleSpecTextChange(event.target.value)}
                placeholder="Generate a draft to start editing."
                value={specText}
              />

              {specParse.error ? (
                <p className="text-sm text-destructive">{specParse.error}</p>
              ) : null}

              {specParse.value ? (
                <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="space-y-1">
                    <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                      Row strategy
                    </dt>
                    <dd className="text-sm font-medium text-foreground">
                      {currentSpecSummary.rowStrategyKind ?? "Not set"}
                    </dd>
                  </div>
                  <div className="space-y-1">
                    <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                      Features
                    </dt>
                    <dd className="text-sm font-medium text-foreground">
                      {currentSpecSummary.featureCount}
                    </dd>
                  </div>
                  <div className="space-y-1">
                    <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                      Output
                    </dt>
                    <dd className="text-sm font-medium text-foreground">
                      {currentSpecSummary.outputFormat
                        ? formatSentenceCase(currentSpecSummary.outputFormat)
                        : "Not set"}
                    </dd>
                  </div>
                  <div className="space-y-1">
                    <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                      Manifest
                    </dt>
                    <dd className="text-sm font-medium text-foreground">
                      {currentSpecSummary.writeManifest === null
                        ? "Not set"
                        : currentSpecSummary.writeManifest
                          ? "Enabled"
                          : "Disabled"}
                    </dd>
                  </div>
                </dl>
              ) : null}

              <div className="flex justify-between gap-2">
                <Button
                  onClick={() => setCreateStep("draft")}
                  type="button"
                  variant="outline"
                >
                  <ArrowLeft className="size-4" />
                  Back
                </Button>
                <Button
                  disabled={specParse.error !== null || !specParse.value}
                  onClick={() => setCreateStep("preview")}
                  type="button"
                >
                  Continue to preview
                  <ArrowRight className="size-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {createStep === "preview" ? (
          <Card className="flex max-h-[calc(100vh-10rem)] flex-col">
            <CardHeader>
              <CardTitle>Preview</CardTitle>
              <CardDescription>
                Review the assembled rows, then save the config and switch to
                the use page.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={
                    isPreviewing ||
                    !selectedSourceAsset ||
                    specParse.error !== null
                  }
                  onClick={runPreview}
                  type="button"
                  variant="outline"
                >
                  {isPreviewing ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <RefreshCcw className="size-4" />
                  )}
                  {isPreviewing ? "Previewing..." : "Preview current spec"}
                </Button>
              </div>

              {previewResponse ? (
                <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="space-y-1">
                      <p className="text-xs tracking-wide text-muted-foreground uppercase">
                        Rows checked
                      </p>
                      <p className="text-sm font-medium text-foreground">
                        {previewResponse.preview.checked_records}
                      </p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs tracking-wide text-muted-foreground uppercase">
                        Bad records
                      </p>
                      <p className="text-sm font-medium text-foreground">
                        {previewResponse.preview.bad_records}
                      </p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs tracking-wide text-muted-foreground uppercase">
                        Preview rows
                      </p>
                      <p className="text-sm font-medium text-foreground">
                        {previewResponse.preview.rows.length}
                      </p>
                    </div>
                  </div>

                  <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
                    {previewResponse.preview.rows.map((row) => (
                      <div
                        key={row.timestamp_ns}
                        className="rounded-lg border bg-muted/20 px-3 py-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <p className="text-sm font-medium text-foreground">
                            Timestamp {row.timestamp_ns}
                          </p>
                          <Badge variant="outline">
                            {Object.keys(row.field_data).length} fields
                          </Badge>
                        </div>
                        <div className="mt-3 grid gap-3 lg:grid-cols-2">
                          <div className="space-y-1">
                            <p className="text-xs tracking-wide text-muted-foreground uppercase">
                              Field data
                            </p>
                            <pre className="overflow-x-auto rounded-md bg-background p-3 font-mono text-xs text-foreground">
                              {stringifyJson(row.field_data)}
                            </pre>
                          </div>
                          <div className="space-y-1">
                            <p className="text-xs tracking-wide text-muted-foreground uppercase">
                              Presence
                            </p>
                            <pre className="overflow-x-auto rounded-md bg-background p-3 font-mono text-xs text-foreground">
                              {stringifyJson(row.presence_data)}
                            </pre>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex min-h-0 flex-1 items-center">
                  <EmptyState
                    variant="card"
                    description="Preview the current spec to see example rows here."
                    title="No preview yet"
                  />
                </div>
              )}

              <div className="flex justify-between gap-2">
                <Button
                  onClick={() => setCreateStep("spec")}
                  type="button"
                  variant="outline"
                >
                  <ArrowLeft className="size-4" />
                  Back
                </Button>
                <Button
                  disabled={isSavingConfig || !previewResponse}
                  onClick={openCreateDialog}
                  type="button"
                >
                  <Save className="size-4" />
                  Save Config
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}

        <ConfigEditorDialog
          description={configDialogDescription}
          dialogMode={configDialogMode}
          isSubmitting={isSavingConfig}
          onDescriptionChange={setConfigDialogDescription}
          onNameChange={setConfigDialogName}
          name={configDialogName}
          open={configDialogMode !== null}
          onOpenChange={(open) => {
            if (!open) {
              setConfigDialogMode(null)
            }
          }}
          onSubmit={() => void submitConfigDialog()}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Button asChild size="sm" variant="ghost">
        <Link href={returnHref}>
          <ArrowLeft className="size-4" />
          Back
        </Link>
      </Button>

      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
                <Sparkles className="size-5" />
                {isCreateMode ? "Create conversion config" : "Use saved config"}
              </h1>
              <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                {selectedAssets.length} selected
              </span>
            </div>
            {isCreateMode ? (
              <p className="max-w-3xl text-sm text-muted-foreground">
                Inspect a source asset, draft a spec, tune the JSON directly,
                preview the result, and save a new config when you are ready.
              </p>
            ) : (
              <p className="max-w-3xl text-sm text-muted-foreground">
                Choose a saved config, review its details, and run it against
                the selected assets.
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {isCreateMode ? (
              <Button
                disabled={isSavingConfig}
                onClick={openCreateDialog}
                size="sm"
                type="button"
                variant="outline"
              >
                <Save className="size-4" />
                Save Config
              </Button>
            ) : (
              <>
                <SavedConfigDropdown
                  configs={savedConfigs}
                  onCreateNew={() =>
                    updateRouteQuery({
                      sourceId: sourceAssetId || null,
                      targetMode: "create",
                    })
                  }
                  onSelectConfig={selectSavedConfig}
                  selectedConfig={selectedConfigSummary}
                />
                <Button
                  disabled={
                    !selectedSavedConfig ||
                    isSubmitting ||
                    isRunningSavedConfig ||
                    unindexedAssets.length > 0
                  }
                  onClick={() => void runSavedConfigConversion()}
                  size="sm"
                  type="button"
                >
                  {isSubmitting || isRunningSavedConfig ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Play className="size-4" />
                  )}
                  Run
                </Button>
              </>
            )}
          </div>
        </div>
      </section>

      {requestMessage ? (
        <Alert
          variant={requestMessage.tone === "error" ? "destructive" : "default"}
        >
          <TriangleAlert className="size-4" />
          <AlertTitle>{requestMessage.title}</AlertTitle>
          {requestMessage.description ? (
            <AlertDescription>{requestMessage.description}</AlertDescription>
          ) : null}
        </Alert>
      ) : null}

      {unindexedAssets.length > 0 ? (
        <Alert variant="destructive">
          <TriangleAlert className="size-4" />
          <AlertTitle>Index assets before converting</AlertTitle>
          <AlertDescription>
            {unindexedAssets
              .slice(0, 3)
              .map((asset) => asset.file_name)
              .join(", ")}
            {unindexedAssets.length > 3
              ? ` and ${unindexedAssets.length - 3} more`
              : ""}{" "}
            must finish indexing before the conversion can run.
          </AlertDescription>
        </Alert>
      ) : null}

      <div
        className={
          isCreateMode
            ? "grid gap-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)]"
            : "space-y-6"
        }
      >
        {isCreateMode ? (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Source asset</CardTitle>
                <CardDescription>
                  Choose the one asset the backend should inspect and draft
                  from.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="source-asset">Source asset</Label>
                  <NativeSelect
                    id="source-asset"
                    onChange={(event) => loadSourceAsset(event.target.value)}
                    value={selectedSourceAsset?.id ?? ""}
                  >
                    {selectedAssets.map((asset) => (
                      <option key={asset.id} value={asset.id}>
                        {asset.file_name}
                      </option>
                    ))}
                  </NativeSelect>
                </div>

                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="space-y-1">
                    <p className="text-xs tracking-wide text-muted-foreground uppercase">
                      File type
                    </p>
                    <p className="text-sm font-medium">
                      {selectedSourceAsset?.file_type ?? "Not available"}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs tracking-wide text-muted-foreground uppercase">
                      Size
                    </p>
                    <p className="text-sm font-medium">
                      {selectedSourceAsset
                        ? formatFileSize(selectedSourceAsset.file_size)
                        : "Not available"}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs tracking-wide text-muted-foreground uppercase">
                      Registered
                    </p>
                    <p className="text-sm font-medium">
                      {selectedSourceAsset
                        ? formatDateTime(selectedSourceAsset.registered_time)
                        : "Not available"}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Inspect</CardTitle>
                <CardDescription>
                  Ask the backend to sample the source asset and infer topic
                  candidates.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <details className="group rounded-lg border bg-muted/20">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-3 [&::-webkit-details-marker]:hidden">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-foreground">
                        Inspect Settings
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Sample count, depth, and decode policy.
                      </p>
                    </div>
                    <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-open:rotate-180" />
                  </summary>
                  <div className="border-t px-3 py-4">
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                      <div className="space-y-2">
                        <Label htmlFor="sample-n">Sample count</Label>
                        <Input
                          id="sample-n"
                          min="1"
                          onChange={(event) =>
                            setInspectionForm((current) => ({
                              ...current,
                              sampleN: event.target.value,
                            }))
                          }
                          type="number"
                          value={inspectionForm.sampleN}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="max-depth">Max depth</Label>
                        <Input
                          id="max-depth"
                          min="0"
                          onChange={(event) =>
                            setInspectionForm((current) => ({
                              ...current,
                              maxDepth: event.target.value,
                            }))
                          }
                          type="number"
                          value={inspectionForm.maxDepth}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="max-sequence-items">
                          Sequence items
                        </Label>
                        <Input
                          id="max-sequence-items"
                          min="1"
                          onChange={(event) =>
                            setInspectionForm((current) => ({
                              ...current,
                              maxSequenceItems: event.target.value,
                            }))
                          }
                          type="number"
                          value={inspectionForm.maxSequenceItems}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="on-failure">Decode failure</Label>
                        <NativeSelect
                          id="on-failure"
                          onChange={(event) =>
                            setInspectionForm((current) => ({
                              ...current,
                              onFailure: event.target
                                .value as DecodeFailurePolicy,
                            }))
                          }
                          value={inspectionForm.onFailure}
                        >
                          <option value="skip">Skip</option>
                          <option value="warn">Warn</option>
                          <option value="fail">Fail</option>
                        </NativeSelect>
                      </div>
                    </div>
                  </div>
                </details>

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="topic-type-hints">Topic type hints</Label>
                    <span className="text-xs text-muted-foreground">
                      {getTopicHintCount(inspectionForm.topicTypeHints) ?? 0}{" "}
                      hints
                    </span>
                  </div>
                  <Textarea
                    id="topic-type-hints"
                    onChange={(event) =>
                      setInspectionForm((current) => ({
                        ...current,
                        topicTypeHints: event.target.value,
                      }))
                    }
                    placeholder='{"\/camera/front/image_raw": "sensor_msgs/msg/Image"}'
                    value={inspectionForm.topicTypeHints}
                  />
                  {topicHintsParse.error ? (
                    <p className="text-sm text-destructive">
                      {topicHintsParse.error}
                    </p>
                  ) : null}
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    disabled={isInspecting || !selectedSourceAsset}
                    onClick={runInspection}
                    type="button"
                  >
                    {isInspecting ? (
                      <LoaderCircle className="size-4 animate-spin" />
                    ) : (
                      <SearchIconFallback />
                    )}
                    {isInspecting ? "Inspecting..." : "Inspect asset"}
                  </Button>
                </div>

                {inspectionWarnings.length > 0 ? (
                  <Alert>
                    <TriangleAlert className="size-4" />
                    <AlertTitle>Inspection warnings</AlertTitle>
                    <AlertDescription>
                      <ul className="mt-2 list-disc space-y-1 pl-5">
                        {inspectionWarnings.map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    </AlertDescription>
                  </Alert>
                ) : null}

                {inspectionResponse ? (
                  <div className="space-y-3">
                    <div className="grid gap-4 sm:grid-cols-3">
                      <div className="space-y-1">
                        <p className="text-xs tracking-wide text-muted-foreground uppercase">
                          ROS version
                        </p>
                        <p className="text-sm font-medium">
                          {inspectionResponse.inspection.ros_version ??
                            "Unknown"}
                        </p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs tracking-wide text-muted-foreground uppercase">
                          Sample count
                        </p>
                        <p className="text-sm font-medium">
                          {inspectionResponse.inspection.sample_n}
                        </p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs tracking-wide text-muted-foreground uppercase">
                          Topics found
                        </p>
                        <p className="text-sm font-medium">
                          {inspectionTopicNames.length}
                        </p>
                      </div>
                    </div>

                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Topic</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Samples</TableHead>
                          <TableHead>Candidates</TableHead>
                          <TableHead>Top fields</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {inspectionTopicNames.map((topicName) => {
                          const topic =
                            inspectionResponse.inspection.topics[topicName]
                          const summary = summarizeInspectionTopic(topic)

                          return (
                            <TableRow key={topicName}>
                              <TableCell className="font-medium">
                                {topicName}
                              </TableCell>
                              <TableCell>
                                {topic.message_type ?? "Unknown"}
                              </TableCell>
                              <TableCell>{summary.sampleCount}</TableCell>
                              <TableCell>{summary.candidateCount}</TableCell>
                              <TableCell className="max-w-[24rem] whitespace-normal">
                                {summary.firstCandidatePaths.length > 0
                                  ? summary.firstCandidatePaths.join(", ")
                                  : "None"}
                              </TableCell>
                            </TableRow>
                          )
                        })}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <EmptyState
                    variant="card"
                    description="Run inspection to see topic candidates and field summaries here."
                    title="No inspection yet"
                  />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Draft</CardTitle>
                <CardDescription>
                  Choose the topics and draft settings the backend should use.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="space-y-2">
                    <Label htmlFor="schema-name">Schema name</Label>
                    <Input
                      id="schema-name"
                      onChange={(event) =>
                        setSpecForm((current) => ({
                          ...current,
                          schemaName: event.target.value,
                        }))
                      }
                      value={specForm.schemaName}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="schema-version">Schema version</Label>
                    <Input
                      id="schema-version"
                      min="1"
                      onChange={(event) =>
                        setSpecForm((current) => ({
                          ...current,
                          schemaVersion: event.target.value,
                        }))
                      }
                      type="number"
                      value={specForm.schemaVersion}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="output-format">Output format</Label>
                    <NativeSelect
                      id="output-format"
                      onChange={(event) =>
                        setSpecForm((current) => ({
                          ...current,
                          outputFormat: event.target.value as ConversionFormat,
                        }))
                      }
                      value={specForm.outputFormat}
                    >
                      <option value="tfrecord">TFRecord</option>
                      <option value="parquet">Parquet</option>
                    </NativeSelect>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="output-compression">Compression</Label>
                    <NativeSelect
                      id="output-compression"
                      onChange={(event) =>
                        setSpecForm((current) => ({
                          ...current,
                          outputCompression: event.target.value,
                        }))
                      }
                      value={specForm.outputCompression}
                    >
                      {specForm.outputFormat === "parquet"
                        ? [
                            "none",
                            "snappy",
                            "gzip",
                            "brotli",
                            "lz4",
                            "zstd",
                          ].map((compression) => (
                            <option key={compression} value={compression}>
                              {formatSentenceCase(compression)}
                            </option>
                          ))
                        : ["none", "gzip"].map((compression) => (
                            <option key={compression} value={compression}>
                              {formatSentenceCase(compression)}
                            </option>
                          ))}
                    </NativeSelect>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="max-features-per-topic">
                      Max features/topic
                    </Label>
                    <Input
                      id="max-features-per-topic"
                      min="1"
                      onChange={(event) =>
                        setSpecForm((current) => ({
                          ...current,
                          maxFeaturesPerTopic: event.target.value,
                        }))
                      }
                      type="number"
                      value={specForm.maxFeaturesPerTopic}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="preview-rows">Preview rows</Label>
                    <Input
                      id="preview-rows"
                      min="1"
                      onChange={(event) =>
                        setSpecForm((current) => ({
                          ...current,
                          previewRows: event.target.value,
                        }))
                      }
                      type="number"
                      value={specForm.previewRows}
                    />
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
                  <div className="space-y-1">
                    <Label htmlFor="label-feature">Label feature</Label>
                    <Input
                      id="label-feature"
                      onChange={(event) =>
                        setSpecForm((current) => ({
                          ...current,
                          labelFeature: event.target.value,
                        }))
                      }
                      placeholder="Optional"
                      value={specForm.labelFeature}
                    />
                  </div>
                  <div className="flex items-center justify-between gap-4 lg:self-center">
                    <Label
                      className="text-sm font-medium text-foreground"
                      htmlFor="include-preview"
                    >
                      Include preview
                    </Label>
                    <Switch
                      checked={specForm.includePreview}
                      id="include-preview"
                      onCheckedChange={(checked) =>
                        setSpecForm((current) => ({
                          ...current,
                          includePreview: checked,
                        }))
                      }
                    />
                  </div>
                </div>

                {inspectionResponse ? (
                  <div className="space-y-3">
                    <div className="space-y-1">
                      <p className="text-xs tracking-wide text-muted-foreground uppercase">
                        Selected topics
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Use picks the topics that will drive the draft. Trigger
                        marks the one topic that should anchor it.
                      </p>
                    </div>

                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-12">Use</TableHead>
                          <TableHead className="w-16">Trigger</TableHead>
                          <TableHead>Topic</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Samples</TableHead>
                          <TableHead>Fields</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {inspectionTopicNames.map((topicName) => {
                          const topic =
                            inspectionResponse.inspection.topics[topicName]
                          const summary = summarizeInspectionTopic(topic)
                          const checked =
                            effectiveSelectedTopics.includes(topicName)
                          const isTrigger = effectiveTriggerTopic === topicName

                          return (
                            <TableRow key={topicName}>
                              <TableCell>
                                <Checkbox
                                  checked={checked}
                                  onCheckedChange={() =>
                                    toggleSelectedTopic(topicName)
                                  }
                                />
                              </TableCell>
                              <TableCell>
                                <Checkbox
                                  checked={isTrigger}
                                  onCheckedChange={(nextChecked) => {
                                    if (nextChecked) {
                                      selectTriggerTopic(topicName)
                                    } else {
                                      clearTriggerTopic(topicName)
                                    }
                                  }}
                                />
                              </TableCell>
                              <TableCell className="font-medium">
                                {topicName}
                              </TableCell>
                              <TableCell>
                                {topic.message_type ?? "Unknown"}
                              </TableCell>
                              <TableCell>{summary.sampleCount}</TableCell>
                              <TableCell className="max-w-[24rem] whitespace-normal">
                                {summary.firstCandidatePaths.length > 0
                                  ? summary.firstCandidatePaths.join(", ")
                                  : "None"}
                              </TableCell>
                            </TableRow>
                          )
                        })}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <EmptyState
                    variant="card"
                    description="Inspect the source asset first so the backend can suggest topics for the draft."
                    title="Draft needs inspection"
                  />
                )}

                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    disabled={
                      isDrafting ||
                      !selectedSourceAsset ||
                      effectiveSelectedTopics.length === 0
                    }
                    onClick={runDraft}
                    type="button"
                  >
                    {isDrafting ? (
                      <LoaderCircle className="size-4 animate-spin" />
                    ) : (
                      <FileJson2 className="size-4" />
                    )}
                    {isDrafting ? "Drafting..." : "Draft spec"}
                  </Button>
                  {draftCompleteIndicator}
                  <Button
                    disabled={
                      isPreviewing ||
                      !selectedSourceAsset ||
                      specParse.error !== null
                    }
                    onClick={runPreview}
                    type="button"
                    variant="outline"
                  >
                    {isPreviewing ? (
                      <LoaderCircle className="size-4 animate-spin" />
                    ) : (
                      <RefreshCcw className="size-4" />
                    )}
                    {isPreviewing ? "Previewing..." : "Preview current spec"}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Spec editor</CardTitle>
                <CardDescription>
                  Keep the contract visible. The backend still validates the
                  real shape.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-xs tracking-wide text-muted-foreground uppercase">
                      Summary
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {currentSpecSummary.schemaName ?? "No spec loaded"}{" "}
                      {currentSpecSummary.schemaVersion !== null
                        ? `v${currentSpecSummary.schemaVersion}`
                        : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      disabled={!draftResponse}
                      onClick={() => {
                        if (draftResponse) {
                          setSpecText(stringifyJson(draftResponse.draft.spec))
                        }
                      }}
                      type="button"
                      variant="outline"
                    >
                      Load draft
                    </Button>
                    <Button
                      disabled={!selectedConfigSpec}
                      onClick={() => {
                        if (selectedConfigSpec) {
                          setSpecText(stringifyJson(selectedConfigSpec))
                        }
                      }}
                      type="button"
                      variant="outline"
                    >
                      Load saved config
                    </Button>
                    <Button
                      disabled={specParse.error !== null}
                      onClick={() => {
                        if (!specParse.value) {
                          return
                        }

                        setSpecText(stringifyJson(specParse.value))
                      }}
                      type="button"
                      variant="outline"
                    >
                      Format JSON
                    </Button>
                  </div>
                </div>

                <Textarea
                  className="min-h-[420px] font-mono text-sm"
                  onChange={(event) => setSpecText(event.target.value)}
                  placeholder="Generate a draft or load a saved config to start editing."
                  value={specText}
                />

                {specParse.error ? (
                  <p className="text-sm text-destructive">{specParse.error}</p>
                ) : null}

                {specParse.value ? (
                  <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <div className="space-y-1">
                      <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                        Row strategy
                      </dt>
                      <dd className="text-sm font-medium text-foreground">
                        {currentSpecSummary.rowStrategyKind ?? "Not set"}
                      </dd>
                    </div>
                    <div className="space-y-1">
                      <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                        Features
                      </dt>
                      <dd className="text-sm font-medium text-foreground">
                        {currentSpecSummary.featureCount}
                      </dd>
                    </div>
                    <div className="space-y-1">
                      <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                        Output
                      </dt>
                      <dd className="text-sm font-medium text-foreground">
                        {currentSpecSummary.outputFormat
                          ? formatSentenceCase(currentSpecSummary.outputFormat)
                          : "Not set"}
                      </dd>
                    </div>
                    <div className="space-y-1">
                      <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                        Manifest
                      </dt>
                      <dd className="text-sm font-medium text-foreground">
                        {currentSpecSummary.writeManifest === null
                          ? "Not set"
                          : currentSpecSummary.writeManifest
                            ? "Enabled"
                            : "Disabled"}
                      </dd>
                    </div>
                  </dl>
                ) : null}
              </CardContent>
            </Card>

            <Card className="flex max-h-[calc(100vh-12rem)] flex-col">
              <CardHeader>
                <CardTitle>Preview</CardTitle>
                <CardDescription>
                  Render the latest draft preview or preview the current spec
                  directly.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex min-h-0 flex-col gap-4">
                {previewResponse ? (
                  <div className="flex min-h-0 flex-1 flex-col gap-4">
                    <div className="grid gap-4 sm:grid-cols-3">
                      <div className="space-y-1">
                        <p className="text-xs tracking-wide text-muted-foreground uppercase">
                          Rows checked
                        </p>
                        <p className="text-sm font-medium text-foreground">
                          {previewResponse.preview.checked_records}
                        </p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs tracking-wide text-muted-foreground uppercase">
                          Bad records
                        </p>
                        <p className="text-sm font-medium text-foreground">
                          {previewResponse.preview.bad_records}
                        </p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs tracking-wide text-muted-foreground uppercase">
                          Preview rows
                        </p>
                        <p className="text-sm font-medium text-foreground">
                          {previewResponse.preview.rows.length}
                        </p>
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-3">
                      <div className="space-y-1">
                        <p className="text-xs tracking-wide text-muted-foreground uppercase">
                          Image payload contract
                        </p>
                        <p className="text-sm font-medium text-foreground">
                          {getImagePayloadContract(authoringRepresentationPolicy)}
                        </p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs tracking-wide text-muted-foreground uppercase">
                          Payload encoding
                        </p>
                        <p className="text-sm font-medium text-foreground">
                          {authoringRepresentationPolicy?.payload_encoding ??
                            "typed_features"}
                        </p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-xs tracking-wide text-muted-foreground uppercase">
                          Null encoding
                        </p>
                        <p className="text-sm font-medium text-foreground">
                          {authoringRepresentationPolicy?.null_encoding ??
                            "presence_flag"}
                        </p>
                      </div>
                    </div>

                    <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
                      {previewResponse.preview.rows.map((row) => (
                        <div
                          key={row.timestamp_ns}
                          className="rounded-lg border bg-muted/20 px-3 py-3"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <p className="text-sm font-medium text-foreground">
                              Timestamp {row.timestamp_ns}
                            </p>
                            <Badge variant="outline">
                              {Object.keys(row.field_data).length} fields
                            </Badge>
                          </div>
                          <div className="mt-3 grid gap-3 lg:grid-cols-2">
                            <div className="space-y-1">
                              <p className="text-xs tracking-wide text-muted-foreground uppercase">
                                Field data
                              </p>
                              <pre className="overflow-x-auto rounded-md bg-background p-3 font-mono text-xs text-foreground">
                                {stringifyJson(row.field_data)}
                              </pre>
                            </div>
                            <div className="space-y-1">
                              <p className="text-xs tracking-wide text-muted-foreground uppercase">
                                Presence
                              </p>
                              <pre className="overflow-x-auto rounded-md bg-background p-3 font-mono text-xs text-foreground">
                                {stringifyJson(row.presence_data)}
                              </pre>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="flex min-h-0 flex-1 items-center">
                    <EmptyState
                      variant="card"
                      description="Preview a draft or the current spec to see example rows here."
                      title="No preview yet"
                    />
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        ) : null}

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Selected config</CardTitle>
              <CardDescription>
                Review migration state, revision history, and the latest
                preview.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedSavedConfig ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-foreground">
                        {selectedSavedConfig.name}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {selectedSavedConfig.description ?? "No description"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        onClick={openUpdateDialog}
                        size="icon"
                        type="button"
                        variant="ghost"
                      >
                        <Save className="size-4" />
                      </Button>
                      <Button
                        onClick={openDuplicateDialog}
                        size="icon"
                        type="button"
                        variant="ghost"
                      >
                        <Copy className="size-4" />
                      </Button>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Badge
                      className={getConfigStatusClasses(
                        selectedSavedConfig.status
                      )}
                      variant={getConfigStatusBadgeVariant(
                        selectedSavedConfig.status
                      )}
                    >
                      {formatSentenceCase(selectedSavedConfig.status)}
                    </Badge>
                    <Badge variant="outline">
                      {selectedSavedConfig.revision_count} revisions
                    </Badge>
                    <Badge variant="outline">
                      {selectedSavedConfig.draft_count} drafts
                    </Badge>
                    {selectedSavedConfig.latest_preview_available ? (
                      <Badge variant="outline">Preview available</Badge>
                    ) : null}
                  </div>

                  {selectedSavedConfig.migration_notes.length > 0 ? (
                    <Alert>
                      <TriangleAlert className="size-4" />
                      <AlertTitle>Migration notes</AlertTitle>
                      <AlertDescription>
                        <ul className="mt-2 list-disc space-y-1 pl-5">
                          {selectedSavedConfig.migration_notes.map((note) => (
                            <li key={note}>{note}</li>
                          ))}
                        </ul>
                      </AlertDescription>
                    </Alert>
                  ) : null}

                  {selectedSavedConfig.invalid_reason ? (
                    <Alert variant="destructive">
                      <TriangleAlert className="size-4" />
                      <AlertTitle>Invalid saved config</AlertTitle>
                      <AlertDescription>
                        {selectedSavedConfig.invalid_reason}
                      </AlertDescription>
                    </Alert>
                  ) : null}

                  <dl className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1">
                      <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                        Schema
                      </dt>
                      <dd className="text-sm font-medium">
                        {selectedSavedConfig.spec_schema_name ??
                          "Not available"}
                        {selectedSavedConfig.spec_schema_version !== null
                          ? ` v${selectedSavedConfig.spec_schema_version}`
                          : ""}
                      </dd>
                    </div>
                    <div className="space-y-1">
                      <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                        Output
                      </dt>
                      <dd className="text-sm font-medium">
                        {selectedSavedConfig.spec_output_format ??
                          "Not available"}
                      </dd>
                    </div>
                    <div className="space-y-1">
                      <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                        Rows
                      </dt>
                      <dd className="text-sm font-medium">
                        {selectedSavedConfig.spec_row_strategy_kind ??
                          "Not available"}
                      </dd>
                    </div>
                    <div className="space-y-1">
                      <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                        Features
                      </dt>
                      <dd className="text-sm font-medium">
                        {selectedSavedConfig.spec_feature_count}
                      </dd>
                    </div>
                    <div className="space-y-1">
                      <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                        Updated
                      </dt>
                      <dd className="text-sm font-medium">
                        {formatDateTime(selectedSavedConfig.updated_at)}
                      </dd>
                    </div>
                    <div className="space-y-1">
                      <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                        Opened
                      </dt>
                      <dd className="text-sm font-medium">
                        {formatDateTime(selectedSavedConfig.last_opened_at)}
                      </dd>
                    </div>
                  </dl>

                  {selectedConfigSpec ? (
                    <div className="space-y-2">
                      <p className="text-xs tracking-wide text-muted-foreground uppercase">
                        Resolved spec summary
                      </p>
                      <dl className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-1">
                          <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                            Schema
                          </dt>
                          <dd className="text-sm font-medium">
                            {selectedConfigSpecSummary.schemaName ??
                              "Not available"}
                          </dd>
                        </div>
                        <div className="space-y-1">
                          <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                            Output
                          </dt>
                          <dd className="text-sm font-medium">
                            {selectedConfigSpecSummary.outputFormat ??
                              "Not available"}
                          </dd>
                        </div>
                        <div className="space-y-1">
                          <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                            Features
                          </dt>
                          <dd className="text-sm font-medium">
                            {selectedConfigSpecSummary.featureCount}
                          </dd>
                        </div>
                        <div className="space-y-1">
                          <dt className="text-xs tracking-wide text-muted-foreground uppercase">
                            Manifest
                          </dt>
                          <dd className="text-sm font-medium">
                            {selectedConfigSpecSummary.writeManifest
                              ? "Enabled"
                              : "Disabled"}
                          </dd>
                        </div>
                      </dl>
                    </div>
                  ) : null}

                  {selectedConfigPreview ? (
                    <div className="space-y-2">
                      <p className="text-xs tracking-wide text-muted-foreground uppercase">
                        Latest preview
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {selectedConfigPreview.rows.length} preview row
                        {selectedConfigPreview.rows.length === 1
                          ? ""
                          : "s"}{" "}
                        available.
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : (
                <EmptyState
                  variant="card"
                  description="Choose a saved config above to review it and access migration notes."
                  title="No config selected"
                />
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <ConfigEditorDialog
        description={configDialogDescription}
        dialogMode={configDialogMode}
        isSubmitting={isSavingConfig}
        onDescriptionChange={setConfigDialogDescription}
        onNameChange={setConfigDialogName}
        name={configDialogName}
        open={configDialogMode !== null}
        onOpenChange={(open) => {
          if (!open) {
            setConfigDialogMode(null)
          }
        }}
        onSubmit={() => void submitConfigDialog()}
      />
    </div>
  )
}

function SearchIconFallback() {
  return <Sparkles className="size-4" />
}
