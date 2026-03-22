import { Suspense } from "react"

import {
  ConversionAuthoringWorkspace,
  ConversionAuthoringWorkspaceFallback,
} from "../conversion-authoring-workspace"

export default function ConversionCreateRoute() {
  return (
    <Suspense fallback={<ConversionAuthoringWorkspaceFallback />}>
      <ConversionAuthoringWorkspace mode="create" />
    </Suspense>
  )
}
