import { Badge } from "@/components/ui/badge";
import type { OutputAvailability } from "@/lib/api";
import { formatOutputAvailability } from "@/lib/format";

export function OutputAvailabilityBadge({ availability }: { availability: OutputAvailability }) {
  const className =
    availability === "ready"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200"
      : availability === "missing"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200"
        : "";

  return (
    <Badge className={className} variant={availability === "invalid" ? "destructive" : "outline"}>
      {formatOutputAvailability(availability)}
    </Badge>
  );
}
