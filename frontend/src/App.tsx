const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000";

function getBackendBaseUrl() {
  const configuredBaseUrl = import.meta.env.VITE_BACKEND_BASE_URL?.trim();
  return configuredBaseUrl || DEFAULT_BACKEND_BASE_URL;
}

export default function App() {
  const backendBaseUrl = getBackendBaseUrl();

  return (
    <main className="min-h-svh bg-background text-foreground">
      <div className="mx-auto flex min-h-svh max-w-5xl flex-col justify-center gap-8 px-6 py-12">
        <div className="space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">
            <span className="size-2 rounded-full bg-emerald-500" />
            Tauri Migration Scaffold
          </div>
          <div className="space-y-3">
            <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
              Hephaes Desktop
            </h1>
            <p className="max-w-3xl text-base leading-7 text-muted-foreground sm:text-lg">
              The desktop shell is now bootstrapped with Vite and Tauri. The
              existing Next.js app remains the primary UI until the route and
              component migration phases land.
            </p>
          </div>
        </div>

        <section className="grid gap-4 md:grid-cols-2">
          <article className="rounded-3xl border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold">Current Phase</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Phase 1 stands up the desktop runtime without changing the current
              user-facing Next app yet.
            </p>
          </article>

          <article className="rounded-3xl border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold">Backend Assumption</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              FastAPI still runs as a separate local process for now.
            </p>
            <code className="mt-4 block rounded-2xl border bg-muted px-3 py-2 text-xs">
              {backendBaseUrl}
            </code>
          </article>
        </section>

        <section className="rounded-[2rem] border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-semibold">What Comes Next</h2>
          <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
            <li>Move shared frontend code into the new desktop source tree.</li>
            <li>Replace Next-specific routing and image/font APIs.</li>
            <li>Port feature routes into React Router inside the desktop app.</li>
          </ol>
        </section>
      </div>
    </main>
  );
}
