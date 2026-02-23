import base64
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

try:
    import orjson as _orjson

    _ORJSON_AVAILABLE = True
except ImportError:  # pragma: no cover
    _orjson = None  # type: ignore[assignment]
    _ORJSON_AVAILABLE = False


@dataclass
class _TopicSamples:
    timestamps: list[int] = field(default_factory=list)
    payloads: list[Any] = field(default_factory=list)

    def append(self, timestamp: int, payload: Any) -> None:
        self.timestamps.append(timestamp)
        self.payloads.append(payload)

    def sort(self) -> None:
        if len(self.timestamps) <= 1:
            return
        order = sorted(range(len(self.timestamps)), key=self.timestamps.__getitem__)
        self.timestamps = [self.timestamps[i] for i in order]
        self.payloads = [self.payloads[i] for i in order]


class JsonPayloadSerializer:
    def dumps(self, payload: Any) -> str:
        if _ORJSON_AVAILABLE:
            return _orjson.dumps(
                payload,
                default=_json_default_orjson,
                option=_orjson.OPT_SERIALIZE_NUMPY | _orjson.OPT_NON_STR_KEYS,
            ).decode()
        return json.dumps(payload, default=_json_default)


class _SparseChunkBuilder:
    def __init__(self, field_names: list[str]) -> None:
        self._field_names = field_names
        self._columns: dict[str, list[str | None]] = {name: [] for name in field_names}
        self.timestamps: list[int] = []
        self.row_count = 0

    def add_row(self, timestamp: int, values: dict[str, str | None]) -> None:
        self.timestamps.append(timestamp)
        self.row_count += 1

        target_len = self.row_count
        for field_name, value in values.items():
            if value is None:
                continue
            column = self._columns[field_name]
            missing = target_len - 1 - len(column)
            if missing > 0:
                column.extend([None] * missing)
            column.append(value)

    def pop_field_data(self) -> dict[str, list[str | None]]:
        if self.row_count == 0:
            return {name: [] for name in self._field_names}

        for field_name in self._field_names:
            column = self._columns[field_name]
            if len(column) < self.row_count:
                column.extend([None] * (self.row_count - len(column)))

        data = self._columns
        self._columns = {name: [] for name in self._field_names}
        self.timestamps = []
        self.row_count = 0
        return data


def _json_default(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (bytes, bytearray)):
        return {
            "__bytes__": True,
            "encoding": "base64",
            "value": base64.b64encode(obj).decode("ascii"),
        }
    if isinstance(obj, set):
        return list(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _json_default_orjson(obj: Any) -> Any:
    if isinstance(obj, (bytes, bytearray)):
        return {
            "__bytes__": True,
            "encoding": "base64",
            "value": base64.b64encode(obj).decode("ascii"),
        }
    if isinstance(obj, set):
        return list(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _encode_raw_payload(raw_payload: bytes) -> str:
    encoded = base64.b64encode(raw_payload).decode("ascii")
    return '{"__bytes__":true,"encoding":"base64","value":"' + encoded + '"}'


def _normalize_payload(payload: Any) -> Any:
    if payload is None or isinstance(payload, (bool, int, float, str)):
        return payload
    if is_dataclass(payload):
        return _normalize_payload(asdict(payload))
    if isinstance(payload, (bytes, bytearray)):
        return {
            "__bytes__": True,
            "encoding": "base64",
            "value": base64.b64encode(payload).decode("ascii"),
        }
    if isinstance(payload, dict):
        return {str(k): _normalize_payload(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_normalize_payload(v) for v in payload]
    if isinstance(payload, set):
        return [_normalize_payload(v) for v in payload]
    if hasattr(payload, "__dict__"):
        return _normalize_payload(payload.__dict__)
    return str(payload)


def _interpolate_json_leaves(lo: Any, hi: Any, alpha: float) -> Any:
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        return lo + alpha * (hi - lo)
    if isinstance(lo, dict) and isinstance(hi, dict):
        return {k: _interpolate_json_leaves(lo[k], hi[k], alpha) for k in lo if k in hi}
    if isinstance(lo, list) and isinstance(hi, list) and len(lo) == len(hi):
        return [_interpolate_json_leaves(a, b, alpha) for a, b in zip(lo, hi)]
    return lo


def _step_ns_from_frequency(freq_hz: float) -> int:
    step_ns = int(round(1e9 / freq_hz))
    if step_ns <= 0:
        raise ValueError("resample frequency is too large to produce a finite grid")
    return step_ns
