# Replay Time-Bounded Reads

## Summary

The replay stack needs lower-latency cursor sampling for playback, scrubber dragging, and synchronized Rerun viewing.
The first dependency is in `hephaes`: the package should expose time-bounded reader APIs so callers can read only the relevant slice of a bag instead of rescanning entire topics on every cursor update.

## Problem

Today the `RosReader` wrapper exposes topic filtering but not explicit `start` and `stop` bounds on:

- `iter_message_headers()`
- `iter_raw_messages()`
- `read_messages()`

The underlying `rosbags` readers already support time-bounded iteration.
Because `hephaes` does not surface that capability, higher layers are forced into broader scans than necessary.

## Goals

- Add bounded-read support without breaking existing callers.
- Keep the API generic so it is useful outside the replay feature.
- Preserve current ordering and payload behavior.
- Match the underlying reader's half-open range semantics.
- Add tests that lock in the new contract.

## Non-Goals

- Implement replay session management in `hephaes`.
- Add websocket logic to `hephaes`.
- Add application-specific caching or database state to `hephaes`.

## Proposed API Changes

Add optional `start_ns` and `stop_ns` keyword arguments to:

- `RosReader.iter_message_headers(topics: list[str] | None = None, *, start_ns: int | None = None, stop_ns: int | None = None)`
- `RosReader.iter_raw_messages(topics: list[str] | None = None, *, start_ns: int | None = None, stop_ns: int | None = None)`
- `RosReader.read_messages(topics: list[str] | None = None, *, start_ns: int | None = None, stop_ns: int | None = None)`

Behavior:

- `start_ns=None` means no lower bound.
- `stop_ns=None` means no upper bound.
- Reads include messages with `timestamp >= start_ns`.
- Reads exclude messages with `timestamp >= stop_ns`.
- Existing callers that do not pass bounds continue to work unchanged.

## Implementation Notes

The wrapper should pass the new bounds through to the underlying `reader.messages(...)` call.
No extra filtering should be added unless the underlying reader raises or does not honor the range.

The methods should continue to:

- filter by topic through `reader.connections`
- preserve timestamp ordering
- deserialize only in `read_messages()`
- leave header and raw iteration fast and lightweight

## Validation And Edge Cases

The new range contract should define behavior for:

- `start_ns == stop_ns`: empty result
- `start_ns > stop_ns`: empty result, not an exception
- topic filters plus bounds
- bounds with no matching messages
- mixed-topic bags where only some topics have data in range

## Testing Strategy

Add unit tests around the `RosReader` contract with fake or fixture-backed readers.
At minimum, cover:

- unbounded behavior remains unchanged
- `start_ns` only
- `stop_ns` only
- `start_ns` plus `stop_ns`
- topic filtering plus time filtering
- empty ranges

If practical, add one regression test around ROS1-style indexed reads and one around ROS2/MCAP-backed reads.

## Downstream Consumers

The backend replay service will use these bounded reads to:

- compute cursor payloads from only the local time window
- support coalesced websocket playback updates
- keep payload selection aligned with the Rerun viewer cursor

## Implementation Tasks

- [ ] Add `start_ns` and `stop_ns` kwargs to `iter_message_headers()`.
- [ ] Add `start_ns` and `stop_ns` kwargs to `iter_raw_messages()`.
- [ ] Add `start_ns` and `stop_ns` kwargs to `read_messages()`.
- [ ] Pass the bounds through to `reader.messages(...)`.
- [ ] Define and document half-open range semantics in code comments or docstrings.
- [ ] Add tests for bounded header iteration.
- [ ] Add tests for bounded raw iteration.
- [ ] Add tests for bounded deserialized iteration.
- [ ] Add tests for topic filtering combined with time bounds.
- [ ] Update `README.md` if the reader API is documented there.
