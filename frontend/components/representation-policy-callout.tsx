import * as React from "react"

import type { ConversionRepresentationPolicy } from "@/lib/api"
import {
  getImagePayloadContract,
  getPolicyVersion,
  getPolicyWarnings,
  isLegacyImagePayloadPolicy,
} from "@/lib/conversion-representation"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { TriangleAlert } from "lucide-react"

export function RepresentationPolicyCallout({
  hasContractMetadata,
  metadataError,
  outputContractLegacyMarker,
  policy,
}: {
  hasContractMetadata: boolean
  metadataError: unknown
  outputContractLegacyMarker: string
  policy: ConversionRepresentationPolicy | null
}) {
  const imagePayloadContract = getImagePayloadContract(policy)
  const isLegacyContract =
    isLegacyImagePayloadPolicy(policy) ||
    Boolean(policy?.compatibility_markers.includes(outputContractLegacyMarker))
  const warnings = getPolicyWarnings(policy)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Image payload contract</CardTitle>
        <CardDescription>
          TFRecord runs are training-first by default and use bytes-backed
          image payload features.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">Policy v{getPolicyVersion(policy)}</Badge>
          <Badge variant={isLegacyContract ? "secondary" : "default"}>
            {imagePayloadContract === "legacy_list_v1"
              ? "Legacy list image payload"
              : "Training-ready bytes payload"}
          </Badge>
          <Badge variant="outline">
            {policy?.output_format === "parquet" ? "Parquet" : "TFRecord"}
          </Badge>
        </div>

        <dl className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1">
            <dt className="text-xs tracking-wide text-muted-foreground uppercase">
              Image payload
            </dt>
            <dd className="text-sm font-medium text-foreground">
              {imagePayloadContract}
            </dd>
          </div>
          <div className="space-y-1">
            <dt className="text-xs tracking-wide text-muted-foreground uppercase">
              Payload encoding
            </dt>
            <dd className="text-sm font-medium text-foreground">
              {policy?.payload_encoding ?? "typed_features"}
            </dd>
          </div>
          <div className="space-y-1">
            <dt className="text-xs tracking-wide text-muted-foreground uppercase">
              Null encoding
            </dt>
            <dd className="text-sm font-medium text-foreground">
              {policy?.null_encoding ?? "presence_flag"}
            </dd>
          </div>
        </dl>

        {metadataError ? (
          <Alert variant="destructive">
            <TriangleAlert className="size-4" />
            <AlertTitle>Schema metadata unavailable</AlertTitle>
            <AlertDescription>
              The backend capabilities endpoint is currently unavailable, so
              contract defaults may be stale until metadata is reachable.
            </AlertDescription>
          </Alert>
        ) : null}

        {!metadataError && !policy && !hasContractMetadata ? (
          <Alert>
            <TriangleAlert className="size-4" />
            <AlertTitle>Waiting for schema metadata</AlertTitle>
            <AlertDescription>
              This backend response did not include representation policy
              metadata yet. The UI is showing safe defaults for mixed-version
              rollout compatibility.
            </AlertDescription>
          </Alert>
        ) : null}

        {isLegacyContract ? (
          <Alert>
            <TriangleAlert className="size-4" />
            <AlertTitle>Legacy compatibility mode detected</AlertTitle>
            <AlertDescription>
              This run uses list-based image payload compatibility. Training
              pipelines expecting bytes features may need fallback logic.
            </AlertDescription>
          </Alert>
        ) : (
          <p className="text-sm text-muted-foreground">
            This contract is optimized for training loaders that expect image
            bytes in TFRecord features.
          </p>
        )}

        {warnings.length > 0 ? (
          <Alert>
            <TriangleAlert className="size-4" />
            <AlertTitle>Contract warnings</AlertTitle>
            <AlertDescription>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  )
}
