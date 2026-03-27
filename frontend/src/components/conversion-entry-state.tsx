import { ArrowLeft } from "lucide-react"

import { AppLink } from "@/lib/app-routing"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

export function ConversionEntryErrorState({
  description,
  returnHref,
}: {
  description: string
  returnHref: string
}) {
  return (
    <div className="space-y-4">
      <Button asChild size="sm" variant="ghost">
        <AppLink href={returnHref}>
          <ArrowLeft className="size-4" />
          Back
        </AppLink>
      </Button>
      <Alert variant="destructive">
        <AlertTitle>Could not load conversion setup</AlertTitle>
        <AlertDescription>
          The app could not load saved conversion configs to decide which
          workflow to open. {description}
        </AlertDescription>
      </Alert>
    </div>
  )
}
