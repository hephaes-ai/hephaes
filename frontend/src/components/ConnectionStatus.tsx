import { useEffect, useState } from "react";

import { apiBaseUrl } from "../lib/config";
import { ApiError, getHealth } from "../lib/api";
import { useFeedback } from "../state/feedback";

type HealthState =
  | { status: "loading" }
  | { status: "healthy"; appName: string }
  | { status: "error"; message: string };

export function ConnectionStatus() {
  const [health, setHealth] = useState<HealthState>({ status: "loading" });
  const { pushFeedback } = useFeedback();

  useEffect(() => {
    const abortController = new AbortController();

    async function loadHealth() {
      setHealth({ status: "loading" });

      try {
        const payload = await getHealth(abortController.signal);
        setHealth({
          status: "healthy",
          appName: payload.app_name || "Backend online",
        });
      } catch (error) {
        if (abortController.signal.aborted) {
          return;
        }

        const message =
          error instanceof ApiError || error instanceof Error
            ? error.message
            : "Unable to reach backend";
        setHealth({ status: "error", message });
        pushFeedback({
          tone: "error",
          message: "Backend connection failed. Start the FastAPI server and reload the page.",
        });
      }
    }

    void loadHealth();

    return () => {
      abortController.abort();
    };
  }, [pushFeedback]);

  return (
    <article className="card status-card">
      <div className="status-row">
        <p className="card-label">Backend</p>
        <span
          className={
            health.status === "healthy"
              ? "status-pill status-pill-success"
              : health.status === "error"
                ? "status-pill status-pill-error"
                : "status-pill"
          }
        >
          {health.status === "healthy"
            ? "Connected"
            : health.status === "error"
              ? "Unavailable"
              : "Checking"}
        </span>
      </div>

      <h2>{apiBaseUrl}</h2>

      {health.status === "healthy" ? (
        <p>{health.appName} is responding to `GET /health`.</p>
      ) : null}
      {health.status === "loading" ? <p>Checking backend health endpoint...</p> : null}
      {health.status === "error" ? <p>{health.message}</p> : null}
    </article>
  );
}
