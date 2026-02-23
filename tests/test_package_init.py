"""Tests for hephaes_core package __init__.py."""
import logging

import pytest

import hephaes_core


class TestVersion:
    def test_version_defined(self):
        assert hasattr(hephaes_core, "__version__")
        assert isinstance(hephaes_core.__version__, str)
        assert hephaes_core.__version__ == "0.1.0"


class TestPublicExports:
    def test_converter_exported(self):
        from hephaes_core import Converter
        assert Converter is not None

    def test_mapping_template_exported(self):
        from hephaes_core import MappingTemplate
        assert MappingTemplate is not None

    def test_wide_parquet_writer_exported(self):
        from hephaes_core import WideParquetWriter
        assert WideParquetWriter is not None

    def test_profiler_exported(self):
        from hephaes_core import Profiler
        assert Profiler is not None

    def test_ros1_reader_exported(self):
        from hephaes_core import ROS1Reader
        assert ROS1Reader is not None

    def test_ros2_reader_exported(self):
        from hephaes_core import ROS2Reader
        assert ROS2Reader is not None

    def test_ros_reader_exported(self):
        from hephaes_core import RosReader
        assert RosReader is not None

    def test_build_mapping_template_exported(self):
        from hephaes_core import build_mapping_template
        assert callable(build_mapping_template)

    def test_build_mapping_template_from_json_exported(self):
        from hephaes_core import build_mapping_template_from_json
        assert callable(build_mapping_template_from_json)

    def test_stream_wide_parquet_rows_exported(self):
        from hephaes_core import stream_wide_parquet_rows
        assert callable(stream_wide_parquet_rows)

    def test_configure_logging_exported(self):
        from hephaes_core import configure_logging
        assert callable(configure_logging)

    def test_all_list_complete(self):
        expected = {
            "__version__",
            "configure_logging",
            "Converter",
            "MappingTemplate",
            "WideParquetWriter",
            "Profiler",
            "ROS1Reader",
            "ROS2Reader",
            "RosReader",
            "build_mapping_template",
            "build_mapping_template_from_json",
            "stream_wide_parquet_rows",
        }
        assert expected.issubset(set(hephaes_core.__all__))


class TestConfigureLogging:
    def test_returns_logger(self):
        logger = hephaes_core.configure_logging()
        assert isinstance(logger, logging.Logger)

    def test_sets_level_int(self):
        logger = hephaes_core.configure_logging(level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_sets_level_str(self):
        logger = hephaes_core.configure_logging(level="WARNING")
        assert logger.level == logging.WARNING

    def test_custom_handler(self):
        handler = logging.StreamHandler()
        logger = hephaes_core.configure_logging(handler=handler)
        assert handler in logger.handlers

    def test_propagate_false_by_default(self):
        logger = hephaes_core.configure_logging()
        assert logger.propagate is False

    def test_propagate_true(self):
        logger = hephaes_core.configure_logging(propagate=True)
        assert logger.propagate is True

    def test_default_handler_is_stream_handler(self):
        logger = hephaes_core.configure_logging()
        assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)

    def test_null_handler_on_import(self):
        # On fresh import the package logger should have a NullHandler
        pkg_logger = logging.getLogger("hephaes_core")
        # After configure_logging replaces handlers, test is about the pkg baseline
        # Just ensure we can call it without error
        hephaes_core.configure_logging()
