import logging

__version__ = "0.1.0"

_PACKAGE_LOGGER_NAME = "hephaes_core"
_package_logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
if not _package_logger.handlers:
    _package_logger.addHandler(logging.NullHandler())
_package_logger.propagate = False


def configure_logging(
    *,
    level: int | str = logging.INFO,
    handler: logging.Handler | None = None,
    propagate: bool = False,
) -> logging.Logger:
    """Configure package logging for hephaes_core modules."""
    logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
    if handler is None:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))

    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = propagate
    return logger


from .converter import Converter
from .mappers import build_mapping_template, build_mapping_template_from_json
from .models import MappingTemplate, ResampleConfig
from .profiler import Profiler
from .reader import ROS1Reader, ROS2Reader, RosReader

__all__ = [
    "__version__",
    "configure_logging",
    "Converter",
    "MappingTemplate",
    "ResampleConfig",
    "WideParquetWriter",
    "Profiler",
    "ROS1Reader",
    "ROS2Reader",
    "RosReader",
    "build_mapping_template",
    "build_mapping_template_from_json",
    "stream_wide_parquet_rows",
]


def __getattr__(name: str):
    if name in {"WideParquetWriter", "stream_wide_parquet_rows"}:
        from .parquet import WideParquetWriter, stream_wide_parquet_rows

        if name == "WideParquetWriter":
            return WideParquetWriter
        return stream_wide_parquet_rows
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
