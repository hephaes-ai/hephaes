export function EmptyState({
  action,
  description,
  title,
  variant = "page",
}: {
  action?: React.ReactNode;
  description: string;
  title: string;
  variant?: "card" | "page";
}) {
  if (variant === "card") {
    return (
      <div className="rounded-lg border border-dashed px-4 py-8 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">{title}</p>
        <p className="mt-2">{description}</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-dashed px-6 py-16 text-center">
      <h2 className="text-sm font-medium text-foreground">{title}</h2>
      <p className="mx-auto mt-2 max-w-2xl text-sm text-muted-foreground">{description}</p>
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}
