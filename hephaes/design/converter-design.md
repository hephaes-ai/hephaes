# MCAP To TFRecord Master Plan

## Summary

The product goal is to turn any MCAP or ROS log into a reusable, training-ready conversion contract.

`hephaes` should own the business logic that lets the backend and frontend help a user inspect data, draft a spec, preview it, save it, reopen it, and convert from it without custom Python glue.

## Goals

- Make the converter config-first instead of helper-function-first.
- Keep the conversion contract explicit, versioned, and editable.
- Support arbitrary MCAP logs, not just known presets.
- Let the user choose how rows are assembled and how fields are encoded.
- Produce outputs that are directly consumable by a training script.
- Keep backend and frontend logic thin by making `hephaes` the source of truth for authoring rules.

## Non-Goals

- Do not hard-code Doom-specific behavior into the generic path.
- Do not make TFRecord writing responsible for discovery, inference, or drafting.
- Do not require a distributed system before the local workflow is useful.

## Target Workflow

```mermaid
flowchart LR
  A["Select MCAP"] --> B["Inspect topics"]
  B --> C["Draft spec"]
  C --> D["Edit config"]
  D --> E["Preview rows"]
  E --> F["Save reusable config"]
  F --> G["Convert"]
```

The workflow should feel like authoring a contract, not writing a script.

## Ownership

### `hephaes` owns

- inspection and inference logic
- draft-spec generation
- preview and validation rules
- config serialization, migration, and capability metadata

### Backend owns

- API contracts
- persistence for reusable configs and drafts
- execution orchestration
- saved resource history and IDs

### Frontend owns

- editing UX
- preview presentation
- saved-config management UX
- routing and page flow

## High-Level Architecture

- `reader.py`: raw log access and decoded message access
- `conversion/decoding.py`: decode policies and type hints
- `conversion/introspection.py`: payload sampling and inference
- `conversion/draft_spec.py`: turn inspection output into editable specs
- `conversion/preview.py`: preview assembled rows and feature outputs
- `converter.py`: execute a finalized spec

## Design Principles

- Declarative first.
- Runtime and authoring should be separate but compatible.
- Capabilities should be discoverable from the library, not duplicated in UI code.
- Built-in presets should be examples, not the primary workflow.
- Versioned specs should survive migration over time.

## Related Docs

- Current state: [`converter-current-state.md`](./converter-current-state.md)
- Active backlog: [`converter-implementation.md`](./converter-implementation.md)
