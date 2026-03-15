import { type FormEvent, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { AssetStatusBadge } from "../components/AssetStatusBadge";
import { ApiError } from "../lib/api";
import { formatDateTime, formatFileSize } from "../lib/format";
import { useFeedback } from "../state/feedback";
import { useInventory } from "../state/inventory";

function isSupportedAssetPath(filePath: string) {
  const normalized = filePath.trim().toLowerCase();
  return normalized.endsWith(".bag") || normalized.endsWith(".mcap");
}

export function InventoryPage() {
  const location = useLocation();
  const [filePath, setFilePath] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { inventory, loadInventory, registerAssetPath } = useInventory();
  const { pushFeedback } = useFeedback();

  useEffect(() => {
    const abortController = new AbortController();
    void loadInventory({ signal: abortController.signal });

    return () => {
      abortController.abort();
    };
  }, [loadInventory]);

  async function handleRegisterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedPath = filePath.trim();
    if (!trimmedPath) {
      setFormError("Enter a local file path to a `.bag` or `.mcap` file.");
      return;
    }

    if (!isSupportedAssetPath(trimmedPath)) {
      setFormError("Only `.bag` and `.mcap` files are supported in this Phase 1 flow.");
      return;
    }

    setFormError(null);
    setIsSubmitting(true);

    try {
      const asset = await registerAssetPath(trimmedPath);
      setFilePath("");
      pushFeedback({
        tone: "info",
        message: `Registered ${asset.file_name} successfully.`,
      });
    } catch (error) {
      const message =
        error instanceof ApiError || error instanceof Error
          ? error.message
          : "Unable to register asset";

      setFormError(message);
      pushFeedback({
        tone: "error",
        message,
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="page-layout">
      <section className="card page-panel">
        <p className="card-label">Inventory</p>
        <h2>Register and browse local ROS log assets.</h2>
        <p>
          This page now uses the real Backend Phase 1 asset endpoints so you can validate the local
          asset-registry flow end to end.
        </p>
      </section>

      <section className="inventory-grid">
        <article className="card panel-card">
          <p className="card-label">Registration</p>
          <h3>Register a `.bag` or `.mcap` file</h3>
          <p>Enter a local file path to add it to the asset inventory.</p>

          <form className="asset-form" onSubmit={handleRegisterSubmit}>
            <label className="field-label" htmlFor="asset-path">
              Local file path
            </label>
            <input
              id="asset-path"
              className="text-input"
              name="filePath"
              type="text"
              value={filePath}
              placeholder="/absolute/path/to/episode.mcap"
              onChange={(event) => setFilePath(event.target.value)}
              disabled={isSubmitting}
            />

            {formError ? <p className="inline-error">{formError}</p> : null}

            <button type="submit" className="primary-button" disabled={isSubmitting}>
              {isSubmitting ? "Registering..." : "Register asset"}
            </button>
          </form>
        </article>

        <article className="card panel-card">
          <div className="inventory-header">
            <div>
              <p className="card-label">Asset inventory</p>
              <h3>Registered assets</h3>
            </div>
            <p className="inventory-count">
              {inventory.assets.length} asset{inventory.assets.length === 1 ? "" : "s"}
            </p>
          </div>

          {inventory.status === "loading" ? (
            <p>Loading asset inventory...</p>
          ) : null}

          {inventory.status === "error" ? (
            <div className="inventory-message">
              <p>{inventory.error}</p>
            </div>
          ) : null}

          {inventory.status === "ready" && inventory.assets.length === 0 ? (
            <div className="inventory-message">
              <p>No assets registered yet.</p>
              <p>Register a `.bag` or `.mcap` file to begin testing the backend flow.</p>
            </div>
          ) : null}

          {inventory.assets.length > 0 ? (
            <div className="table-wrap">
              <table className="asset-table">
                <thead>
                  <tr>
                    <th>File name</th>
                    <th>Type</th>
                    <th>Size</th>
                    <th>Status</th>
                    <th>Registered</th>
                    <th>Last indexed</th>
                  </tr>
                </thead>
                <tbody>
                  {inventory.assets.map((asset) => (
                    <tr key={asset.id}>
                      <td>
                        <Link
                          to={`/assets/${asset.id}`}
                          state={{ returnTo: `${location.pathname}${location.search}` }}
                          className="asset-link"
                        >
                          {asset.file_name}
                        </Link>
                        <p className="asset-path">{asset.file_path}</p>
                      </td>
                      <td>{asset.file_type}</td>
                      <td>{formatFileSize(asset.file_size)}</td>
                      <td>
                        <AssetStatusBadge status={asset.indexing_status} />
                      </td>
                      <td>{formatDateTime(asset.registered_time)}</td>
                      <td>{formatDateTime(asset.last_indexed_time)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </article>
      </section>
    </main>
  );
}
