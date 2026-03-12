# Changelog

All notable changes to this project will be documented in this file.

This changelog is intentionally lightweight and focuses on user-visible changes:
new capabilities, behavior changes, bug fixes, and anything that affects dataset
correctness or compatibility.

## [0.2.0] - Unreleased

### Added

- TFRecord output support, including `TFRecordOutputConfig` and
  `stream_tfrecord_rows(...)` for reading converted examples back in Python.
- A pluggable output writer layer that separates conversion from format-specific
  writers, making it easier to add new dataset targets over time.
- Parquet image extraction helpers for recovering image-like payloads stored as
  base64-wrapped JSON bytes.

### Changed

- Clarified the project scope and API in the README around profiling logs,
  mapping source topics into stable dataset fields, and converting logs into
  wide Parquet or TFRecord datasets.
- Continued the converter/output refactor so one input log produces one dataset
  file with a consistent per-row schema across output formats.
- Standardized the published package version and runtime package version on
  `0.2.0`.

### Fixed

- Fixed TFRecord signed integer round-tripping so negative `int64` values decode
  correctly instead of appearing as large unsigned integers.
- Fixed TFRecord sequence round-tripping so singleton sequences such as `[5]`
  stay sequences instead of collapsing into scalars.
- Fixed TFRecord empty-sequence round-tripping so empty lists can be recovered
  as `[]` instead of disappearing during decode.
