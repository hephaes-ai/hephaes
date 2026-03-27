import logging

from ._version import __version__

_PACKAGE_LOGGER_NAME = "hephaes"
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
    """Configure package logging for hephaes modules."""
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
from .conversion.capabilities import ConversionCapabilities, build_conversion_capabilities
from .conversion.draft_spec import DraftSpecRequest, DraftSpecResult, build_draft_conversion_spec
from .conversion.introspection import (
    FieldCandidate,
    InspectionRequest,
    InspectionResult,
    SampledMessage,
    TopicInspectionResult,
    inspect_bag,
    inspect_reader,
)
from .conversion.assembly import ConstructedRowRecord, RowConstructionResult, construct_rows
from .conversion.features import FeatureEvaluationContext, source_input_topics
from .conversion.preview import PreviewResult, PreviewRow, preflight_conversion_spec, preview_conversion_spec
from .conversion.spec_io import (
    CONVERSION_SPEC_DOCUMENT_VERSION,
    ConversionSpecDocument,
    build_conversion_spec_document,
    dump_conversion_spec,
    dump_conversion_spec_document,
    load_conversion_spec,
    load_conversion_spec_document,
    migrate_conversion_spec_document,
    migrate_conversion_spec_payload,
    set_tfrecord_image_payload_contract,
)
from .models import (
    AssemblySpec,
    ConcatSourceSpec,
    ConstantSourceSpec,
    ConversionSpec,
    DecodingSpec,
    DraftOriginSpec,
    FieldSourceSpec,
    FeatureSourceSpec,
    FeatureSpec,
    InputDiscoverySpec,
    JoinSpec,
    LabelSpec,
    MappingTemplate,
    MetadataSourceSpec,
    MissingDataPolicy,
    OutputSpec,
    ParquetOutputConfig,
    PerMessageRowStrategySpec,
    ResampleConfig,
    ResampleRowStrategySpec,
    RowStrategySpec,
    SchemaSpec,
    SplitSpec,
    StackSourceSpec,
    TFRecordOutputConfig,
    TopicDecodeSpec,
    TransformSpec,
    ValidationSpec,
    build_doom_ros_train_py_compatible,
    build_legacy_conversion_spec,
    build_single_trigger_sensor_log_template,
)
from .profiler import Profiler
from .reader import ROS1Reader, ROS2Reader, RosReader
from .workspace import (
    AssetAlreadyRegisteredError,
    AssetNotFoundError,
    ConversionConfigAlreadyExistsError,
    ConversionConfigInvalidError,
    ConversionConfigNotFoundError,
    DefaultEpisodeSummary,
    IndexedAssetMetadata,
    IndexedTopicSummary,
    InvalidAssetPathError,
    OutputArtifact,
    OutputArtifactNotFoundError,
    OutputArtifactSummary,
    RegisteredAsset,
    SavedConversionConfig,
    SavedConversionConfigSummary,
    SourceAssetMetadata,
    TagAlreadyExistsError,
    TagNotFoundError,
    VisualizationSummary,
    WorkspaceTag,
    Workspace,
    WorkspaceAlreadyExistsError,
    WorkspaceError,
    WorkspaceNotFoundError,
)

__all__ = [
    "__version__",
    "configure_logging",
    "Converter",
    "CONVERSION_SPEC_DOCUMENT_VERSION",
    "ConversionCapabilities",
    "DraftSpecRequest",
    "DraftSpecResult",
    "ConstructedRowRecord",
    "FeatureEvaluationContext",
    "AssemblySpec",
    "ConcatSourceSpec",
    "ConstantSourceSpec",
    "ConversionSpec",
    "ConversionSpecDocument",
    "DecodingSpec",
    "DraftOriginSpec",
    "FieldCandidate",
    "FieldSourceSpec",
    "FeatureSourceSpec",
    "FeatureSpec",
    "InputDiscoverySpec",
    "InspectionRequest",
    "InspectionResult",
    "JoinSpec",
    "LabelSpec",
    "MappingTemplate",
    "MetadataSourceSpec",
    "MissingDataPolicy",
    "PreviewResult",
    "PreviewRow",
    "RowConstructionResult",
    "OutputSpec",
    "ParquetOutputConfig",
    "PerMessageRowStrategySpec",
    "ResampleConfig",
    "ResampleRowStrategySpec",
    "RowStrategySpec",
    "SchemaSpec",
    "SplitSpec",
    "SampledMessage",
    "StackSourceSpec",
    "TFRecordOutputConfig",
    "TopicDecodeSpec",
    "TopicInspectionResult",
    "TransformSpec",
    "ValidationSpec",
    "WideParquetWriter",
    "Profiler",
    "ConversionConfigAlreadyExistsError",
    "ConversionConfigInvalidError",
    "ConversionConfigNotFoundError",
    "DefaultEpisodeSummary",
    "IndexedAssetMetadata",
    "IndexedTopicSummary",
    "RegisteredAsset",
    "OutputArtifact",
    "OutputArtifactNotFoundError",
    "OutputArtifactSummary",
    "ROS1Reader",
    "ROS2Reader",
    "RosReader",
    "AssetNotFoundError",
    "SavedConversionConfig",
    "SavedConversionConfigSummary",
    "SourceAssetMetadata",
    "TagAlreadyExistsError",
    "TagNotFoundError",
    "VisualizationSummary",
    "WorkspaceTag",
    "Workspace",
    "WorkspaceAlreadyExistsError",
    "WorkspaceError",
    "WorkspaceNotFoundError",
    "InvalidAssetPathError",
    "AssetAlreadyRegisteredError",
    "build_mapping_template",
    "build_mapping_template_from_json",
    "build_conversion_capabilities",
    "build_conversion_spec_document",
    "build_draft_conversion_spec",
    "build_doom_ros_train_py_compatible",
    "build_legacy_conversion_spec",
    "construct_rows",
    "dump_conversion_spec",
    "dump_conversion_spec_document",
    "inspect_bag",
    "inspect_reader",
    "load_conversion_spec",
    "load_conversion_spec_document",
    "migrate_conversion_spec_document",
    "migrate_conversion_spec_payload",
    "set_tfrecord_image_payload_contract",
    "preflight_conversion_spec",
    "preview_conversion_spec",
    "source_input_topics",
    "build_single_trigger_sensor_log_template",
    "stream_wide_parquet_rows",
    "stream_tfrecord_rows",
]


def __getattr__(name: str):
    if name in {"WideParquetWriter", "stream_wide_parquet_rows"}:
        from .parquet import WideParquetWriter, stream_wide_parquet_rows

        if name == "WideParquetWriter":
            return WideParquetWriter
        return stream_wide_parquet_rows
    if name == "stream_tfrecord_rows":
        from .tfrecord import stream_tfrecord_rows

        return stream_tfrecord_rows
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
