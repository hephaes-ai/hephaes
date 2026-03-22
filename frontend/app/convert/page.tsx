import { Suspense } from "react";

import {
  ConversionAuthoringWorkspace,
  ConversionAuthoringWorkspaceFallback,
} from "./conversion-authoring-workspace";

export default function ConversionRoute() {
  return (
    <Suspense fallback={<ConversionAuthoringWorkspaceFallback />}>
      <ConversionAuthoringWorkspace />
    </Suspense>
  );
}
