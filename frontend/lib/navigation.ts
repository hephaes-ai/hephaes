export function resolveReturnHref(from: string | null | undefined, fallbackHref: string) {
  if (!from) {
    return fallbackHref;
  }

  // Keep return navigation local to this app.
  if (!from.startsWith("/") || from.startsWith("//")) {
    return fallbackHref;
  }

  return from;
}
