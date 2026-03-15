import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { AssetStatusBadge } from "../components/AssetStatusBadge";
import { ApiError, getAsset, type AssetSummary } from "../lib/api";
import { formatDateTime, formatFileSize } from "../lib/format";

type DetailState =
  | { status: "loading"; asset: AssetSummary | null; error: string | null }
  | { status: "ready"; asset: AssetSummary; error: null }
  | { status: "not-found"; asset: null; error: string }
  | { status: "error"; asset: null; error: string };

export function AssetDetailPage() {
  const { assetId } = useParams<{ assetId: string }>();
  const location = useLocation();
  const [detailState, setDetailState] = useState<DetailState>({
    status: "loading",
    asset: null,
    error: null,
  });
  const returnTo =
    typeof location.state === "object" &&
    location.state !== null &&
    "returnTo" in location.state &&
    typeof location.state.returnTo === "string"
      ? location.state.returnTo
      : "/";

  useEffect(() => {
    const abortController = new AbortController();

    async function loadAsset() {
      if (!assetId) {
        setDetailState({
          status: "not-found",
          asset: null,
          error: "No asset ID was provided in the route.",
        });
        return;
      }

      setDetailState({
        status: "loading",
        asset: null,
        error: null,
      });

      try {
        const response = await getAsset(assetId, abortController.signal);
        setDetailState({
          status: "ready",
          asset: response.asset,
          error: null,
        });
      } catch (error) {
        if (abortController.signal.aborted) {
          return;
        }

        if (error instanceof ApiError && error.status === 404) {
          setDetailState({
            status: "not-found",
            asset: null,
            error: error.message,
          });
          return;
        }

        const message =
          error instanceof ApiError || error instanceof Error
            ? error.message
            : "Unable to load asset detail";

        setDetailState({
          status: "error",
          asset: null,
          error: message,
        });
      }
    }

    void loadAsset();

    return () => {
      abortController.abort();
    };
  }, [assetId]);

  if (detailState.status === "loading") {
    return (
      <main className="page-layout">
        <section className="card page-panel">
          <p className="card-label">Asset detail</p>
          <h2>Loading asset...</h2>
          <p>Fetching the current asset from the backend.</p>
        </section>
      </main>
    );
  }

  if (detailState.status === "not-found") {
    return (
      <main className="page-layout">
        <section className="card page-panel">
          <p className="card-label">Asset detail</p>
          <h2>Asset not found.</h2>
          <p>{detailState.error}</p>
          <Link to={returnTo} className="back-link">
            Return to inventory
          </Link>
        </section>
      </main>
    );
  }

  if (detailState.status === "error") {
    return (
      <main className="page-layout">
        <section className="card page-panel">
          <p className="card-label">Asset detail</p>
          <h2>Unable to load this asset.</h2>
          <p>{detailState.error}</p>
          <Link to={returnTo} className="back-link">
            Return to inventory
          </Link>
        </section>
      </main>
    );
  }

  const asset = detailState.asset;

  return (
    <main className="page-layout">
      <section className="card page-panel">
        <p className="card-label">Asset detail</p>
        <h2>{asset.file_name}</h2>
        <p>{asset.file_path}</p>
      </section>

      <section className="detail-grid">
        <article className="card detail-card">
          <p className="card-label">Base file information</p>
          <h3>Current backend detail payload</h3>

          <dl className="detail-list">
            <div>
              <dt>File name</dt>
              <dd>{asset.file_name}</dd>
            </div>
            <div>
              <dt>File path</dt>
              <dd className="detail-path">{asset.file_path}</dd>
            </div>
            <div>
              <dt>File type</dt>
              <dd>{asset.file_type}</dd>
            </div>
            <div>
              <dt>File size</dt>
              <dd>{formatFileSize(asset.file_size)}</dd>
            </div>
            <div>
              <dt>Registered</dt>
              <dd>{formatDateTime(asset.registered_time)}</dd>
            </div>
            <div>
              <dt>Last indexed</dt>
              <dd>{formatDateTime(asset.last_indexed_time)}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                <AssetStatusBadge status={asset.indexing_status} />
              </dd>
            </div>
            <div>
              <dt>Asset ID</dt>
              <dd>{asset.id}</dd>
            </div>
          </dl>
        </article>

        <article className="card detail-card">
          <p className="card-label">Future phase placeholders</p>
          <h3>Metadata, tags, conversions</h3>
          <p>
            This panel is intentionally reserved for indexed metadata, tags, and conversion history
            once later backend phases are implemented.
          </p>

          <ul className="detail-placeholder-list">
            <li>Metadata fields will render here after indexing exists.</li>
            <li>Tag management will live here once tag APIs are available.</li>
            <li>Conversion history and job links will be added in later phases.</li>
          </ul>
        </article>
      </section>

      <Link to={returnTo} className="back-link">
        Return to inventory
      </Link>
    </main>
  );
}
