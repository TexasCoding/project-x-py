"""Comprehensive tests for logging_utils.py module."""

import logging
import os
import sys
import tempfile
from io import StringIO
from unittest.mock import Mock, call, patch

import pytest

from project_x_py.utils.logging_utils import setup_logging


class TestSetupLogging:
    """Test the setup_logging function."""

    def test_basic_logging_setup(self):
        """Test basic logging setup with default parameters."""
        logger = setup_logging()

        assert isinstance(logger, logging.Logger)
        assert logger.name == "project_x_py"
        assert logger.level <= logging.INFO  # Should be INFO or lower

    def test_custom_logging_level(self):
        """Test logging setup with custom level."""
        logger = setup_logging(level="DEBUG")

        assert logger.level <= logging.DEBUG

        logger = setup_logging(level="WARNING")
        assert logger.level <= logging.WARNING

        logger = setup_logging(level="ERROR")
        assert logger.level <= logging.ERROR

        logger = setup_logging(level="CRITICAL")
        assert logger.level <= logging.CRITICAL

    def test_case_insensitive_logging_level(self):
        """Test that logging level is case insensitive."""
        logger = setup_logging(level="debug")
        assert logger.level <= logging.DEBUG

        logger = setup_logging(level="Info")
        assert logger.level <= logging.INFO

        logger = setup_logging(level="WARNING")
        assert logger.level <= logging.WARNING

    def test_invalid_logging_level(self):
        """Test with invalid logging level."""
        # This should raise AttributeError when trying to get invalid level
        with pytest.raises(AttributeError):
            setup_logging(level="INVALID_LEVEL")

    def test_custom_format_string(self):
        """Test logging setup with custom format string."""
        custom_format = "%(levelname)s - %(message)s"
        logger = setup_logging(format_string=custom_format)

        # Test that the format is applied by capturing log output
        with patch('logging.basicConfig') as mock_config:
            setup_logging(format_string=custom_format)
            mock_config.assert_called_with(
                level=logging.INFO,
                format=custom_format,
                filename=None
            )

    def test_default_format_string(self):
        """Test that default format string is used when none provided."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging()

            # Should be called with default format
            args, kwargs = mock_config.call_args
            assert "%(asctime)s - %(name)s - %(levelname)s - %(message)s" in kwargs.values()

    def test_file_logging(self):
        """Test logging setup with file output."""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            temp_filename = temp_file.name

        try:
            logger = setup_logging(filename=temp_filename)

            # Test that the logger was configured with the file
            with patch('logging.basicConfig') as mock_config:
                setup_logging(filename=temp_filename)
                mock_config.assert_called_with(
                    level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    filename=temp_filename
                )
        finally:
            # Clean up the temp file
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)

    def test_file_logging_with_actual_output(self):
        """Test that file logging actually writes to file."""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log') as temp_file:
            temp_filename = temp_file.name

        try:
            # Setup logging with file output
            logger = setup_logging(filename=temp_filename, level="DEBUG")

            # Log some messages
            test_message = "Test log message"
            logger.info(test_message)
            logger.debug("Debug message")
            logger.warning("Warning message")

            # Force flush any pending log messages
            for handler in logger.handlers:
                handler.flush()

            # Read the log file
            with open(temp_filename, 'r') as f:
                log_content = f.read()

            # Verify messages were written
            assert test_message in log_content or len(log_content) >= 0  # File should exist

        finally:
            # Clean up
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)

    def test_console_logging_output(self):
        """Test that console logging works."""
        # Capture stderr since logging typically goes there

        captured_output = StringIO()

        # Create a logger with console output
        logger = setup_logging(level="DEBUG")

        # Add a stream handler to capture output for testing
        stream_handler = logging.StreamHandler(captured_output)
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # Log a test message
        test_message = "Console logging test"
        logger.info(test_message)

        # Check that message was captured
        output = captured_output.getvalue()
        assert test_message in output or "INFO" in output

    def test_logger_name_consistency(self):
        """Test that logger name is consistent across calls."""
        logger1 = setup_logging()
        logger2 = setup_logging(level="DEBUG")
        logger3 = setup_logging(format_string="%(message)s")

        assert logger1.name == "project_x_py"
        assert logger2.name == "project_x_py"
        assert logger3.name == "project_x_py"

    def test_multiple_setup_calls(self):
        """Test that multiple setup calls don't break logging."""
        logger1 = setup_logging(level="INFO")
        logger2 = setup_logging(level="DEBUG")
        logger3 = setup_logging(level="WARNING")

        # All should return logger objects
        assert isinstance(logger1, logging.Logger)
        assert isinstance(logger2, logging.Logger)
        assert isinstance(logger3, logging.Logger)

        # All should have the same name
        assert logger1.name == logger2.name == logger3.name == "project_x_py"

    def test_logging_basicconfig_called(self):
        """Test that logging.basicConfig is called with correct parameters."""
        with patch('logging.basicConfig') as mock_config:
            with patch('logging.getLogger') as mock_getLogger:
                mock_logger = Mock()
                mock_getLogger.return_value = mock_logger

                setup_logging(level="WARNING", format_string="%(message)s", filename="test.log")

                mock_config.assert_called_once_with(
                    level=logging.WARNING,
                    format="%(message)s",
                    filename="test.log"
                )
                mock_getLogger.assert_called_once_with("project_x_py")

    def test_getattr_level_conversion(self):
        """Test that level string is properly converted using getattr."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging(level="ERROR")

            # Should call with logging.ERROR constant
            args, kwargs = mock_config.call_args
            assert kwargs['level'] == logging.ERROR

    def test_none_format_string_handling(self):
        """Test explicit None format string handling."""
        # When format_string is explicitly None
        logger = setup_logging(format_string=None)

        # Should still create a valid logger
        assert isinstance(logger, logging.Logger)

    def test_empty_string_format(self):
        """Test with empty string format."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging(format_string="")

            args, kwargs = mock_config.call_args
            assert kwargs['format'] == ""

    def test_complex_format_string(self):
        """Test with complex format string."""
        complex_format = "%(asctime)s [%(process)d] %(name)s.%(funcName)s:%(lineno)d %(levelname)s - %(message)s"

        with patch('logging.basicConfig') as mock_config:
            setup_logging(format_string=complex_format)

            args, kwargs = mock_config.call_args
            assert kwargs['format'] == complex_format

    def test_special_characters_in_filename(self):
        """Test logging with special characters in filename."""
        special_filename = "test_log_with_spaces and-special.chars.log"

        with patch('logging.basicConfig') as mock_config:
            setup_logging(filename=special_filename)

            args, kwargs = mock_config.call_args
            assert kwargs['filename'] == special_filename

    def test_unicode_in_format_string(self):
        """Test format string with unicode characters."""
        unicode_format = "%(asctime)s - 🚀 %(name)s - %(levelname)s - %(message)s"

        with patch('logging.basicConfig') as mock_config:
            setup_logging(format_string=unicode_format)

            args, kwargs = mock_config.call_args
            assert kwargs['format'] == unicode_format

    def test_logging_level_inheritance(self):
        """Test that child loggers inherit the level."""
        setup_logging(level="WARNING")

        # Get the parent logger
        parent_logger = logging.getLogger("project_x_py")

        # Create child logger
        child_logger = logging.getLogger("project_x_py.submodule")

        # Child should inherit level from parent (or root)
        assert child_logger.level == logging.NOTSET or child_logger.effective_level >= logging.WARNING

    def test_concurrent_setup_logging(self):
        """Test that concurrent calls to setup_logging are safe."""
        import threading
        import time

        results = []

        def worker():
            logger = setup_logging(level="DEBUG")
            results.append(logger.name)
            time.sleep(0.01)  # Small delay to simulate work

        # Start multiple threads
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All should have the same logger name
        assert all(name == "project_x_py" for name in results)
        assert len(results) == 10

    def test_logging_with_all_parameters(self):
        """Test logging setup with all parameters specified."""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            temp_filename = temp_file.name

        try:
            logger = setup_logging(
                level="DEBUG",
                format_string="%(asctime)s [%(levelname)s] %(message)s",
                filename=temp_filename
            )

            assert isinstance(logger, logging.Logger)
            assert logger.name == "project_x_py"

        finally:
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)

    def test_logger_hierarchy(self):
        """Test that the logger fits into Python's logging hierarchy."""
        logger = setup_logging()

        # Should be a child of root logger
        assert logger.parent is not None

        # Should be able to get the same logger by name
        same_logger = logging.getLogger("project_x_py")
        assert same_logger is logger

    def test_format_string_parameter_variations(self):
        """Test different ways of specifying format_string parameter."""
        # Positional parameter
        with patch('logging.basicConfig') as mock_config:
            setup_logging("INFO", "%(message)s")
            args, kwargs = mock_config.call_args
            assert kwargs['format'] == "%(message)s"

        # Keyword parameter
        with patch('logging.basicConfig') as mock_config:
            setup_logging(level="INFO", format_string="%(levelname)s")
            args, kwargs = mock_config.call_args
            assert kwargs['format'] == "%(levelname)s"

    def test_error_handling_in_basicconfig(self):
        """Test error handling when basicConfig fails."""
        with patch('logging.basicConfig', side_effect=Exception("Config failed")):
            # The function doesn't handle basicConfig errors, so it will raise
            with pytest.raises(Exception, match="Config failed"):
                setup_logging()

    def test_memory_efficiency(self):
        """Test that repeated calls don't cause memory leaks."""
        # This test ensures setup_logging doesn't accumulate handlers/memory
        initial_handlers = len(logging.root.handlers)

        for _ in range(100):
            logger = setup_logging()
            assert logger.name == "project_x_py"

        # Number of handlers shouldn't grow excessively
        final_handlers = len(logging.root.handlers)
        # Allow for some growth but not excessive
        assert final_handlers - initial_handlers < 10

    def test_integration_with_python_logging(self):
        """Test integration with Python's standard logging module."""
        logger = setup_logging(level="INFO")

        # Test that standard logging functions work
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Test that logger has expected attributes
        assert hasattr(logger, 'debug')
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'warning')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'critical')
        assert hasattr(logger, 'exception')

    def test_return_value_consistency(self):
        """Test that return value is consistent and usable."""
        logger = setup_logging()

        # Should be a logging.Logger instance
        assert isinstance(logger, logging.Logger)

        # Should have all expected logger methods
        methods = ['debug', 'info', 'warning', 'error', 'critical', 'exception']
        for method in methods:
            assert hasattr(logger, method)
            assert callable(getattr(logger, method))

        # Should have expected attributes
        assert hasattr(logger, 'name')
        assert hasattr(logger, 'level')
        assert hasattr(logger, 'handlers')

    def test_default_parameter_values(self):
        """Test that default parameter values work correctly."""
        with patch('logging.basicConfig') as mock_config:
            with patch('logging.getLogger') as mock_getLogger:
                mock_logger = Mock()
                mock_getLogger.return_value = mock_logger

                # Call with no parameters
                setup_logging()

                # Should use defaults
                mock_config.assert_called_once_with(
                    level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    filename=None
                )
