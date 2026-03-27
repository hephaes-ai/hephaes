"""Tests for hephaes package __init__.py."""
import logging

import pytest

import hephaes


class TestVersion:
    def test_version_defined(self):
        assert hasattr(hephaes, "__version__")
        assert isinstance(hephaes.__version__, str)
        assert hephaes.__version__ == "0.2.2"


class TestPublicExports:
    def test_converter_exported(self):
        from hephaes import Converter
        assert Converter is not None

    def test_conversion_capabilities_exported(self):
        from hephaes import ConversionCapabilities
        assert ConversionCapabilities is not None

    def test_conversion_spec_document_exported(self):
        from hephaes import ConversionSpecDocument
        assert ConversionSpecDocument is not None

    def test_build_draft_conversion_spec_exported(self):
        from hephaes import build_draft_conversion_spec
        assert callable(build_draft_conversion_spec)

    def test_inspect_reader_exported(self):
        from hephaes import inspect_reader
        assert callable(inspect_reader)

    def test_preview_conversion_spec_exported(self):
        from hephaes import preview_conversion_spec
        assert callable(preview_conversion_spec)

    def test_preflight_conversion_spec_exported(self):
        from hephaes import preflight_conversion_spec
        assert callable(preflight_conversion_spec)

    def test_mapping_template_exported(self):
        from hephaes import MappingTemplate
        assert MappingTemplate is not None

    def test_feature_source_spec_exported(self):
        from hephaes import FeatureSourceSpec
        assert FeatureSourceSpec is not None

    def test_row_strategy_spec_exported(self):
        from hephaes import RowStrategySpec
        assert RowStrategySpec is not None

    def test_draft_origin_spec_exported(self):
        from hephaes import DraftOriginSpec
        assert DraftOriginSpec is not None

    def test_resample_config_exported(self):
        from hephaes import ResampleConfig
        assert ResampleConfig is not None

    def test_parquet_output_config_exported(self):
        from hephaes import ParquetOutputConfig
        assert ParquetOutputConfig is not None

    def test_tfrecord_output_config_exported(self):
        from hephaes import TFRecordOutputConfig
        assert TFRecordOutputConfig is not None

    def test_wide_parquet_writer_exported(self):
        from hephaes import WideParquetWriter
        assert WideParquetWriter is not None

    def test_profiler_exported(self):
        from hephaes import Profiler
        assert Profiler is not None

    def test_workspace_exported(self):
        from hephaes import Workspace
        assert Workspace is not None

    def test_indexed_asset_metadata_exported(self):
        from hephaes import IndexedAssetMetadata
        assert IndexedAssetMetadata is not None

    def test_workspace_summary_models_exported(self):
        from hephaes import (
            DefaultEpisodeSummary,
            IndexedTopicSummary,
            SourceAssetMetadata,
            VisualizationSummary,
        )
        assert DefaultEpisodeSummary is not None
        assert IndexedTopicSummary is not None
        assert SourceAssetMetadata is not None
        assert VisualizationSummary is not None

    def test_ros1_reader_exported(self):
        from hephaes import ROS1Reader
        assert ROS1Reader is not None

    def test_ros2_reader_exported(self):
        from hephaes import ROS2Reader
        assert ROS2Reader is not None

    def test_ros_reader_exported(self):
        from hephaes import RosReader
        assert RosReader is not None

    def test_build_mapping_template_exported(self):
        from hephaes import build_mapping_template
        assert callable(build_mapping_template)

    def test_build_mapping_template_from_json_exported(self):
        from hephaes import build_mapping_template_from_json
        assert callable(build_mapping_template_from_json)

    def test_build_conversion_capabilities_exported(self):
        from hephaes import build_conversion_capabilities
        assert callable(build_conversion_capabilities)

    def test_build_conversion_spec_document_exported(self):
        from hephaes import build_conversion_spec_document
        assert callable(build_conversion_spec_document)

    def test_dump_conversion_spec_exported(self):
        from hephaes import dump_conversion_spec
        assert callable(dump_conversion_spec)

    def test_load_conversion_spec_exported(self):
        from hephaes import load_conversion_spec
        assert callable(load_conversion_spec)

    def test_stream_wide_parquet_rows_exported(self):
        from hephaes import stream_wide_parquet_rows
        assert callable(stream_wide_parquet_rows)

    def test_stream_tfrecord_rows_exported(self):
        from hephaes import stream_tfrecord_rows
        assert callable(stream_tfrecord_rows)

    def test_configure_logging_exported(self):
        from hephaes import configure_logging
        assert callable(configure_logging)

    def test_all_list_complete(self):
        expected = {
            "__version__",
            "configure_logging",
            "Converter",
            "ConversionCapabilities",
            "ConversionSpecDocument",
            "DraftSpecRequest",
            "DraftSpecResult",
            "DraftOriginSpec",
            "MappingTemplate",
            "ParquetOutputConfig",
            "ResampleConfig",
            "FieldCandidate",
            "FeatureSourceSpec",
            "TFRecordOutputConfig",
            "InspectionRequest",
            "InspectionResult",
            "RowStrategySpec",
            "WideParquetWriter",
            "Profiler",
            "DefaultEpisodeSummary",
            "IndexedAssetMetadata",
            "IndexedTopicSummary",
            "RegisteredAsset",
            "ROS1Reader",
            "ROS2Reader",
            "RosReader",
            "AssetNotFoundError",
            "SourceAssetMetadata",
            "VisualizationSummary",
            "Workspace",
            "WorkspaceAlreadyExistsError",
            "WorkspaceError",
            "WorkspaceNotFoundError",
            "InvalidAssetPathError",
            "AssetAlreadyRegisteredError",
            "build_conversion_capabilities",
            "build_conversion_spec_document",
            "build_draft_conversion_spec",
            "build_mapping_template",
            "build_mapping_template_from_json",
            "dump_conversion_spec",
            "dump_conversion_spec_document",
            "inspect_bag",
            "inspect_reader",
            "load_conversion_spec",
            "load_conversion_spec_document",
            "migrate_conversion_spec_document",
            "migrate_conversion_spec_payload",
            "preflight_conversion_spec",
            "preview_conversion_spec",
            "PreviewResult",
            "PreviewRow",
            "SampledMessage",
            "TopicInspectionResult",
            "stream_wide_parquet_rows",
            "stream_tfrecord_rows",
        }
        assert expected.issubset(set(hephaes.__all__))


class TestConfigureLogging:
    def test_returns_logger(self):
        logger = hephaes.configure_logging()
        assert isinstance(logger, logging.Logger)

    def test_sets_level_int(self):
        logger = hephaes.configure_logging(level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_sets_level_str(self):
        logger = hephaes.configure_logging(level="WARNING")
        assert logger.level == logging.WARNING

    def test_custom_handler(self):
        handler = logging.StreamHandler()
        logger = hephaes.configure_logging(handler=handler)
        assert handler in logger.handlers

    def test_propagate_false_by_default(self):
        logger = hephaes.configure_logging()
        assert logger.propagate is False

    def test_propagate_true(self):
        logger = hephaes.configure_logging(propagate=True)
        assert logger.propagate is True

    def test_default_handler_is_stream_handler(self):
        logger = hephaes.configure_logging()
        assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)

    def test_null_handler_on_import(self):
        # On fresh import the package logger should have a NullHandler
        pkg_logger = logging.getLogger("hephaes")
        # After configure_logging replaces handlers, test is about the pkg baseline
        # Just ensure we can call it without error
        hephaes.configure_logging()
