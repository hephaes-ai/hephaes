from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image

from ..models import TransformSpec


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return value
    raise TypeError("transform expects a sequence value")


def _map_numeric_value(value: Any, fn) -> Any:
    if isinstance(value, np.ndarray):
        return _map_numeric_value(value.tolist(), fn)
    if isinstance(value, list):
        return [_map_numeric_value(item, fn) for item in value]
    if isinstance(value, tuple):
        return [_map_numeric_value(item, fn) for item in value]
    if isinstance(value, bool):
        return fn(int(value))
    if isinstance(value, (int, float, np.generic)) and not isinstance(value, bool):
        return fn(value.item() if isinstance(value, np.generic) else value)
    return value


def _cast_scalar(value: Any, dtype: str) -> Any:
    if dtype == "bytes":
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, str):
            return value.encode("utf-8")
        if isinstance(value, (list, tuple)):
            return bytes(value)
        raise TypeError("cannot cast value to bytes")
    if dtype == "bool":
        return bool(value)
    if dtype == "int64":
        return int(value)
    if dtype in {"float32", "float64"}:
        return float(value)
    if dtype == "json":
        return value
    raise ValueError(f"unsupported dtype: {dtype}")


def _apply_cast(value: Any, params: dict[str, Any]) -> Any:
    dtype = params.get("dtype")
    if not isinstance(dtype, str) or not dtype.strip():
        raise ValueError("cast transform requires a dtype")
    dtype = dtype.strip()

    if isinstance(value, np.ndarray):
        value = value.tolist()

    if isinstance(value, (list, tuple)):
        return [_apply_cast(item, params) for item in value]

    return _cast_scalar(value, dtype)


def _apply_length(value: Any, params: dict[str, Any]) -> Any:
    sequence = _as_list(value)

    exact = params.get("exact")
    if exact is not None:
        exact = int(exact)
        if len(sequence) != exact:
            raise ValueError(f"expected sequence length {exact}, got {len(sequence)}")
        return sequence

    pad_to = params.get("pad_to")
    truncate_to = params.get("truncate_to")
    pad_value = params.get("pad_value", params.get("value", 0))

    if pad_to is not None:
        pad_to = int(pad_to)
        if len(sequence) > pad_to:
            sequence = sequence[:pad_to]
        elif len(sequence) < pad_to:
            sequence = sequence + [pad_value] * (pad_to - len(sequence))

    if truncate_to is not None:
        truncate_to = int(truncate_to)
        if len(sequence) > truncate_to:
            sequence = sequence[:truncate_to]

    min_length = params.get("min")
    if min_length is not None and len(sequence) < int(min_length):
        raise ValueError(f"expected sequence length >= {int(min_length)}, got {len(sequence)}")

    max_length = params.get("max")
    if max_length is not None and len(sequence) > int(max_length):
        raise ValueError(f"expected sequence length <= {int(max_length)}, got {len(sequence)}")

    return sequence


def _apply_clamp(value: Any, params: dict[str, Any]) -> Any:
    min_value = params.get("min")
    max_value = params.get("max")

    def _clamp_number(item: Any) -> Any:
        current = item
        if min_value is not None:
            current = max(current, min_value)
        if max_value is not None:
            current = min(current, max_value)
        return current

    return _map_numeric_value(value, _clamp_number)


def _apply_scale(value: Any, params: dict[str, Any]) -> Any:
    scale = params.get("scale")
    if scale is None:
        scale = params.get("factor", 1)
    offset = params.get("offset", 0)

    def _scale_number(item: Any) -> Any:
        return (item - offset) * scale

    return _map_numeric_value(value, _scale_number)


def _apply_normalize(value: Any, params: dict[str, Any]) -> Any:
    mean = params.get("mean", 0)
    std = params.get("std")
    scale = params.get("scale")
    min_value = params.get("min")
    max_value = params.get("max")

    def _normalize_number(item: Any) -> Any:
        current = item
        if min_value is not None and max_value is not None:
            span = max_value - min_value
            if span == 0:
                raise ValueError("normalize transform requires min and max to differ")
            current = (current - min_value) / span
        else:
            current = current - mean
            if std is not None:
                if std == 0:
                    raise ValueError("normalize transform requires std to be non-zero")
                current = current / std
            if scale is not None:
                current = current / scale
        return current

    return _map_numeric_value(value, _normalize_number)


def _apply_one_hot(value: Any, params: dict[str, Any]) -> list[int]:
    depth = params.get("depth", params.get("size"))
    if depth is None:
        raise ValueError("one_hot transform requires a depth")
    depth = int(depth)
    index = int(value)
    if index < 0 or index >= depth:
        raise ValueError(f"one_hot index {index} is out of range for depth {depth}")
    result = [0] * depth
    result[index] = 1
    return result


def _apply_multi_hot(value: Any, params: dict[str, Any]) -> list[int]:
    depth = params.get("depth", params.get("size"))
    if depth is None:
        raise ValueError("multi_hot transform requires a depth")
    depth = int(depth)
    result = [0] * depth
    values = value if isinstance(value, (list, tuple, np.ndarray)) else [value]
    for item in values:
        index = int(item)
        if index < 0 or index >= depth:
            raise ValueError(f"multi_hot index {index} is out of range for depth {depth}")
        result[index] = 1
    return result


def _to_image_array(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    if isinstance(value, (list, tuple)):
        return np.asarray(value)
    if isinstance(value, (bytes, bytearray)):
        return np.frombuffer(value, dtype=np.uint8)
    if isinstance(value, dict):
        if "data" in value:
            return _to_image_array(value["data"])
        if "pixels" in value:
            return _to_image_array(value["pixels"])
    raise TypeError("image transform expects an array-like value")


def _reshape_image_array(array: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    if array.ndim >= 2:
        return array

    channels = params.get("channels")
    if channels is None:
        source_format = str(params.get("from", "")).lower()
        channels = {"gray": 1, "grey": 1, "l": 1, "rgb": 3, "bgr": 3, "rgba": 4, "bgra": 4}.get(
            source_format
        )

    if channels is None:
        if array.size == 0:
            return array.reshape((0, 0))
        return array.reshape((1, array.size, 1))

    channels = int(channels)
    if channels <= 0:
        raise ValueError("image transform requires channels to be positive")
    if array.size % channels != 0:
        raise ValueError("image payload size does not match the requested channel count")

    pixels = array.size // channels
    height = params.get("height")
    width = params.get("width")
    if height is not None and width is not None:
        height = int(height)
        width = int(width)
        if height * width != pixels:
            raise ValueError("image payload size does not match height and width")
        return array.reshape((height, width, channels))

    return array.reshape((1, pixels, channels))


def _convert_channel_order(array: np.ndarray, source_format: str, target_format: str) -> np.ndarray:
    source_format = source_format.lower()
    target_format = target_format.lower()

    if source_format == target_format:
        return array

    if array.ndim == 2 and target_format in {"rgb", "bgr"}:
        return np.stack([array, array, array], axis=-1)

    if array.ndim != 3:
        raise ValueError("image color conversion requires a 2D or 3D image array")

    if source_format in {"rgb", "bgr"} and target_format in {"rgb", "bgr"}:
        if source_format == target_format:
            return array
        return array[..., ::-1]

    if source_format in {"rgba", "bgra"} and target_format in {"rgb", "bgr"}:
        reordered = array[..., :3]
        if source_format == "bgra":
            reordered = reordered[..., ::-1]
        elif source_format == "rgba" and target_format == "bgr":
            reordered = reordered[..., ::-1]
        return reordered

    if source_format in {"rgb", "bgr"} and target_format in {"rgba", "bgra"}:
        if source_format == "bgr":
            reordered = array[..., ::-1]
        else:
            reordered = array
        alpha = np.full((*reordered.shape[:2], 1), 255, dtype=reordered.dtype)
        if target_format == "bgra":
            reordered = reordered[..., ::-1]
        return np.concatenate([reordered, alpha], axis=-1)

    if source_format in {"rgba", "bgra"} and target_format in {"rgba", "bgra"}:
        if source_format == target_format:
            return array
        return array[..., [2, 1, 0, 3]]

    if target_format == "gray" and array.ndim == 3:
        return np.mean(array[..., :3], axis=-1).astype(array.dtype)

    raise ValueError(f"unsupported image color conversion: {source_format} -> {target_format}")


def _apply_image_color_convert(value: Any, params: dict[str, Any]) -> list[Any]:
    source_format = params.get("from")
    target_format = params.get("to")
    if not isinstance(source_format, str) or not source_format.strip():
        raise ValueError("image_color_convert requires a 'from' format")
    if not isinstance(target_format, str) or not target_format.strip():
        raise ValueError("image_color_convert requires a 'to' format")

    array = _to_image_array(value)
    array = _reshape_image_array(array, params)
    converted = _convert_channel_order(array, source_format.strip(), target_format.strip())
    return converted.tolist()


def _apply_image_resize(value: Any, params: dict[str, Any]) -> list[Any]:
    width = params.get("width")
    height = params.get("height")
    size = params.get("size")
    if size is not None:
        if isinstance(size, (list, tuple)) and len(size) == 2:
            width, height = size
        else:
            raise ValueError("resize transform requires size to be a [width, height] pair")
    if width is None or height is None:
        raise ValueError("resize transform requires width and height")

    array = _to_image_array(value)
    array = _reshape_image_array(array, params)
    image = Image.fromarray(np.asarray(array).astype(np.uint8))
    resized = image.resize((int(width), int(height)))
    return np.asarray(resized).tolist()


def _apply_image_crop(value: Any, params: dict[str, Any]) -> list[Any]:
    array = _to_image_array(value)
    array = _reshape_image_array(array, params)

    box = params.get("box")
    if box is not None:
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            raise ValueError("crop transform requires box to be [left, top, right, bottom]")
        left, top, right, bottom = [int(item) for item in box]
    else:
        left = int(params.get("left", 0))
        top = int(params.get("top", 0))
        crop_width = params.get("width")
        crop_height = params.get("height")
        if crop_width is None or crop_height is None:
            raise ValueError("crop transform requires a box or width and height")
        right = left + int(crop_width)
        bottom = top + int(crop_height)

    cropped = array[top:bottom, left:right]
    return cropped.tolist()


def _apply_image_encode(value: Any, params: dict[str, Any]) -> bytes:
    image_format = params.get("format", "png")
    if not isinstance(image_format, str) or not image_format.strip():
        raise ValueError("image_encode requires a format")

    if isinstance(value, (bytes, bytearray)):
        return bytes(value)

    array = _to_image_array(value)
    array = _reshape_image_array(array, params)
    np_array = np.asarray(array)

    if np_array.ndim == 2:
        mode = "L"
    elif np_array.ndim == 3:
        channels = np_array.shape[2]
        if channels == 1:
            np_array = np_array[..., 0]
            mode = "L"
        elif channels == 3:
            mode = "RGB"
        elif channels == 4:
            mode = "RGBA"
        else:
            raise ValueError(f"unsupported image channel count for encoding: {channels}")
    else:
        raise ValueError("image_encode expects a 2D or 3D image array")

    buffer = BytesIO()
    Image.fromarray(np.asarray(np_array).astype(np.uint8), mode=mode).save(
        buffer,
        format=image_format.strip().upper(),
    )
    return buffer.getvalue()


def apply_transform(value: Any, transform: TransformSpec) -> Any:
    params = dict(transform.params)
    kind = transform.kind

    if kind == "cast":
        return _apply_cast(value, params)
    if kind == "length":
        return _apply_length(value, params)
    if kind == "clamp":
        return _apply_clamp(value, params)
    if kind == "scale":
        return _apply_scale(value, params)
    if kind == "normalize":
        return _apply_normalize(value, params)
    if kind == "one_hot":
        return _apply_one_hot(value, params)
    if kind == "multi_hot":
        return _apply_multi_hot(value, params)
    if kind == "image_color_convert":
        return _apply_image_color_convert(value, params)
    if kind == "image_resize":
        return _apply_image_resize(value, params)
    if kind == "image_crop":
        return _apply_image_crop(value, params)
    if kind == "image_encode":
        return _apply_image_encode(value, params)

    raise ValueError(f"unsupported transform kind: {kind}")


def apply_transform_chain(value: Any, transforms: list[TransformSpec]) -> Any:
    for transform in transforms:
        value = apply_transform(value, transform)
    return value
