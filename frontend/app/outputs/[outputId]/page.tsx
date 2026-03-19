import { redirect } from "next/navigation";

export default async function OutputDetailRoute({
  params,
  searchParams,
}: {
  params: Promise<{ outputId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { outputId } = await params;
  const incomingSearchParams = await searchParams;
  const nextParams = new URLSearchParams();

  for (const [key, value] of Object.entries(incomingSearchParams)) {
    if (key === "output") {
      continue;
    }

    if (Array.isArray(value)) {
      for (const item of value) {
        nextParams.append(key, item);
      }
      continue;
    }

    if (typeof value === "string") {
      nextParams.set(key, value);
    }
  }

  nextParams.set("output", outputId);
  redirect(`/outputs?${nextParams.toString()}`);
}
