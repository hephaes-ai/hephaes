"use client";

import { Badge } from "@/components/ui/badge";
import { useHealth } from "@/hooks/use-backend";

export function BackendStatus() {
  const { data, error, isLoading } = useHealth();

  if (error) {
    return (
      <Badge className="gap-1.5" variant="destructive">
        <span className="size-1.5 rounded-full bg-current" />
        Backend unavailable
      </Badge>
    );
  }

  if (isLoading) {
    return (
      <Badge className="gap-1.5" variant="secondary">
        <span className="size-1.5 rounded-full bg-current/70" />
        Checking backend
      </Badge>
    );
  }

  return (
    <Badge className="gap-1.5 border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200" variant="outline">
      <span className="size-1.5 rounded-full bg-emerald-500" />
      {data?.app_name ?? "Backend"} online
    </Badge>
  );
}
