import { redirect } from "next/navigation"

import { ConversionEntryErrorState } from "@/components/conversion-entry-state"
import { resolveConversionEntry } from "@/lib/conversion-entry"
import { resolveReturnHref } from "@/lib/navigation"

export const dynamic = "force-dynamic"

function appendSearchParams(
  searchParams: Record<string, string | string[] | undefined>,
  nextParams: URLSearchParams
) {
  for (const [key, value] of Object.entries(searchParams)) {
    if (Array.isArray(value)) {
      for (const item of value) {
        nextParams.append(key, item)
      }
      continue
    }

    if (typeof value === "string") {
      nextParams.set(key, value)
    }
  }
}

export default async function ConversionRoute({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const params = await searchParams
  const nextParams = new URLSearchParams()
  appendSearchParams(params, nextParams)
  const resolution = await resolveConversionEntry(nextParams)

  if (resolution.status === "error") {
    return (
      <ConversionEntryErrorState
        description={resolution.error}
        returnHref={resolveReturnHref(nextParams.get("from"), "/inventory")}
      />
    )
  }

  redirect(resolution.href)
}
