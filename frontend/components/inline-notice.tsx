import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function InlineNotice({
  description,
  title,
  tone,
}: {
  description?: string;
  title: string;
  tone: "error" | "info" | "success";
}) {
  const className =
    tone === "success"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200"
      : tone === "info"
        ? "border-border bg-card"
        : "";

  return (
    <Alert className={className} variant={tone === "error" ? "destructive" : "default"}>
      <AlertTitle>{title}</AlertTitle>
      {description ? <AlertDescription>{description}</AlertDescription> : null}
    </Alert>
  );
}
