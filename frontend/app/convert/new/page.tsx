import { Suspense } from "react"

import {
  ConversionAuthoringWorkspace,
  ConversionAuthoringWorkspaceFallback,
} from "@/features/convert/conversion-authoring-workspace"

export default function ConversionCreateRoute() {
  return (
    <Suspense fallback={<ConversionAuthoringWorkspaceFallback />}>
      <ConversionAuthoringWorkspace mode="create" />
    </Suspense>
  )
}
