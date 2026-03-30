# Hephaes

![Inventory](assets/dashboard-031926.png)

Hephaes is a local-first open-source robotics log indexing and dataset conversion stack,
built to turn raw ROS and MCAP logs into clean, searchable, reproducible datasets on
your own machine.

## Core Workflow

- register local `.bag` and `.mcap` logs by file path or directory scan
- index logs to extract duration, start and end time, topic summaries, message counts, sensor types, and raw metadata
- browse assets in a sortable/filterable inventory with tags and indexing status
- inspect each asset in a detail page with topic breakdowns, related jobs, and conversion history
- convert selected sessions to Parquet or TFRecord with custom mappings, compression, resampling, and manifests
- browse generated outputs and open artifact content directly
- track durable jobs for indexing and conversion

## Quick Start

Requires [Rust](https://www.rust-lang.org/tools/install), Node.js, and Python 3.11+.

```bash
pip install -r requirements.txt
cd frontend && npm install
npm run tauri:dev:sidecar
```

## Enterprise Features

We are also building features for enterprise that sit on top of the local OSS core.

Planned enterprise features include:

- cloud ingestion from buckets, remote URLs, and managed connectors
- multi-user authentication, organizations, workspaces, roles, and ownership
- shared catalogs with team-wide browsing and admin views
- saved searches, shared presets, and richer metadata search
- managed conversion jobs with retries, scheduling, and distributed execution
- first-class named datasets with versioning, sharing, approvals, and publishing
- dataset lineage with hashes, creators, schema governance, and audit history
- remote replay and visualization with access control and collaboration
- team workflows for outputs, approvals, integrations, and downstream compute actions

If you are interested in being a design partner, please reach out to hello@hephaes.ai

## Repository Layout

- `frontend/`: React + Vite UI with a Tauri desktop shell
- `backend/`: FastAPI service
- `hephaes/`: Python package for log inspection and dataset conversion
- `docs/`: project documentation site (Nextra)

## Python Setup

```bash
pip install -r requirements.txt
```

Or individually:

```bash
pip install -e "./hephaes[dev]"
pip install -e "./backend[dev]"
```
