import { Suspense } from "react"

import {
  ConversionAuthoringWorkspace,
  ConversionAuthoringWorkspaceFallback,
} from "../conversion-authoring-workspace"

export default function ConversionUseRoute() {
  return (
    <Suspense fallback={<ConversionAuthoringWorkspaceFallback />}>
      <ConversionAuthoringWorkspace mode="use" />
    </Suspense>
  )
}
