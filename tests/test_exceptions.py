"""
Comprehensive tests for the exceptions module.

Tests all exception classes, edge cases, and error handling scenarios.
Targets 100% coverage of the exceptions.py module.
"""

import json
import pickle
import sys
from contextlib import suppress
from typing import Any

import pytest

from project_x_py.exceptions import (
    InvalidOrderParameters,
    ProjectXAuthenticationError,
    ProjectXClientError,
    ProjectXConnectionError,
    ProjectXDataError,
    ProjectXError,
    ProjectXInstrumentError,
    ProjectXOrderError,
    ProjectXPositionError,
    ProjectXRateLimitError,
    ProjectXServerError,
    RiskLimitExceeded,
)


class TestProjectXError:
    """Test the base ProjectXError exception."""

    def test_create_with_message_only(self):
        """Test creating exception with just a message."""
        error = ProjectXError("Test error message")
        assert str(error) == "Test error message"
        assert error.error_code is None
        assert error.response_data == {}

    def test_create_with_error_code(self):
        """Test creating exception with error code."""
        error = ProjectXError("Test error", error_code=500)
        assert str(error) == "Test error"
        assert error.error_code == 500
        assert error.response_data == {}

    def test_create_with_response_data(self):
        """Test creating exception with response data."""
        data = {"status": "error", "details": "Something went wrong"}
        error = ProjectXError("Test error", response_data=data)
        assert str(error) == "Test error"
        assert error.error_code is None
        assert error.response_data == data

    def test_create_with_all_parameters(self):
        """Test creating exception with all parameters."""
        data = {"status": "error", "code": 500}
        error = ProjectXError("Test error", error_code=500, response_data=data)
        assert str(error) == "Test error"
        assert error.error_code == 500
        assert error.response_data == data

    def test_inheritance_from_exception(self):
        """Test that ProjectXError inherits from Exception."""
        error = ProjectXError("Test")
        assert isinstance(error, Exception)
        assert isinstance(error, ProjectXError)

    def test_can_be_raised_and_caught(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(ProjectXError) as exc_info:
            raise ProjectXError("Test error", error_code=123)

        assert str(exc_info.value) == "Test error"
        assert exc_info.value.error_code == 123

    def test_can_be_caught_as_exception(self):
        """Test that exception can be caught as generic Exception."""
        try:
            raise ProjectXError("Test")
        except Exception as e:
            assert isinstance(e, ProjectXError)
            assert str(e) == "Test"


class TestProjectXErrorEdgeCases:
    """Test edge cases for ProjectXError."""

    def test_empty_message(self):
        """Test creating exception with empty message."""
        error = ProjectXError("")
        assert str(error) == ""

    def test_very_long_message(self):
        """Test creating exception with very long message."""
        long_message = "x" * 100000
        error = ProjectXError(long_message)
        assert str(error) == long_message
        assert len(str(error)) == 100000

    def test_unicode_message(self):
        """Test creating exception with unicode characters."""
        unicode_message = "Error: 错误 🚨 エラー"
        error = ProjectXError(unicode_message)
        assert str(error) == unicode_message

    def test_error_code_zero(self):
        """Test error code as zero."""
        error = ProjectXError("Test", error_code=0)
        assert error.error_code == 0

    def test_error_code_negative(self):
        """Test negative error code."""
        error = ProjectXError("Test", error_code=-999)
        assert error.error_code == -999

    def test_error_code_large_number(self):
        """Test very large error code."""
        large_code = sys.maxsize
        error = ProjectXError("Test", error_code=large_code)
        assert error.error_code == large_code

    def test_response_data_nested(self):
        """Test response data with nested structures."""
        nested_data = {
            "level1": {
                "level2": {
                    "level3": ["item1", "item2"],
                    "data": {"key": "value"}
                }
            }
        }
        error = ProjectXError("Test", response_data=nested_data)
        assert error.response_data == nested_data

    def test_response_data_with_none_values(self):
        """Test response data containing None values."""
        data = {"key1": None, "key2": "value", "key3": None}
        error = ProjectXError("Test", response_data=data)
        assert error.response_data == data

    def test_response_data_mixed_types(self):
        """Test response data with mixed types."""
        data = {
            "string": "text",
            "number": 123,
            "float": 45.67,
            "bool": True,
            "list": [1, 2, 3],
            "none": None
        }
        error = ProjectXError("Test", response_data=data)
        assert error.response_data == data


class TestDerivedExceptions:
    """Test all derived exception classes."""

    @pytest.mark.parametrize("exception_class", [
        ProjectXAuthenticationError,
        ProjectXRateLimitError,
        ProjectXServerError,
        ProjectXClientError,
        ProjectXConnectionError,
        ProjectXDataError,
        ProjectXOrderError,
        ProjectXPositionError,
        ProjectXInstrumentError,
        RiskLimitExceeded,
        InvalidOrderParameters,
    ])
    def test_derived_exception_creation(self, exception_class):
        """Test creating each derived exception."""
        error = exception_class("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, ProjectXError)
        assert isinstance(error, Exception)
        assert error.error_code is None
        assert error.response_data == {}

    @pytest.mark.parametrize("exception_class", [
        ProjectXAuthenticationError,
        ProjectXRateLimitError,
        ProjectXServerError,
        ProjectXClientError,
        ProjectXConnectionError,
        ProjectXDataError,
        ProjectXOrderError,
        ProjectXPositionError,
        ProjectXInstrumentError,
        RiskLimitExceeded,
        InvalidOrderParameters,
    ])
    def test_derived_exception_with_all_params(self, exception_class):
        """Test creating derived exceptions with all parameters."""
        data = {"error": "details"}
        error = exception_class("Test", error_code=500, response_data=data)
        assert str(error) == "Test"
        assert error.error_code == 500
        assert error.response_data == data

    @pytest.mark.parametrize("exception_class", [
        ProjectXAuthenticationError,
        ProjectXRateLimitError,
        ProjectXServerError,
        ProjectXClientError,
        ProjectXConnectionError,
        ProjectXDataError,
        ProjectXOrderError,
        ProjectXPositionError,
        ProjectXInstrumentError,
        RiskLimitExceeded,
        InvalidOrderParameters,
    ])
    def test_derived_exception_inheritance(self, exception_class):
        """Test inheritance chain for derived exceptions."""
        error = exception_class("Test")

        # Should be instance of itself
        assert isinstance(error, exception_class)

        # Should be instance of ProjectXError
        assert isinstance(error, ProjectXError)

        # Should be instance of Exception
        assert isinstance(error, Exception)

        # Can be caught as ProjectXError
        try:
            raise error
        except ProjectXError as e:
            assert e is error

    def test_specific_exception_scenarios(self):
        """Test specific scenarios for each exception type."""
        # Authentication error
        auth_error = ProjectXAuthenticationError(
            "Invalid credentials",
            error_code=401,
            response_data={"reason": "token_expired"}
        )
        assert auth_error.error_code == 401

        # Rate limit error
        rate_error = ProjectXRateLimitError(
            "Too many requests",
            error_code=429,
            response_data={"retry_after": 60}
        )
        assert rate_error.response_data["retry_after"] == 60

        # Server error
        server_error = ProjectXServerError(
            "Internal server error",
            error_code=500
        )
        assert server_error.error_code == 500

        # Order error
        order_error = ProjectXOrderError(
            "Invalid order quantity",
            response_data={"min_quantity": 1, "max_quantity": 100}
        )
        assert "min_quantity" in order_error.response_data


class TestExceptionHandling:
    """Test exception handling scenarios."""

    def test_raise_from_another_exception(self):
        """Test raising ProjectX exception from another exception."""
        try:
            try:
                _ = 1 / 0  # Fixed: assigned to variable
            except ZeroDivisionError as e:
                raise ProjectXDataError("Data processing failed") from e
        except ProjectXDataError as e:
            assert str(e) == "Data processing failed"
            assert e.__cause__.__class__.__name__ == "ZeroDivisionError"

    def test_exception_chaining(self):
        """Test exception chaining."""
        try:
            try:
                raise ProjectXConnectionError("Connection lost")
            except ProjectXConnectionError as conn_err:
                raise ProjectXServerError("Server unavailable") from conn_err
        except ProjectXServerError as e:
            assert str(e) == "Server unavailable"

    def test_contextlib_suppress(self):
        """Test using exceptions with contextlib.suppress."""
        with suppress(ProjectXRateLimitError):
            raise ProjectXRateLimitError("Rate limited")

        # Should not raise
        assert True

    async def test_async_exception_handling(self):
        """Test exception handling in async context."""
        async def async_function():
            raise ProjectXOrderError("Async order error")

        with pytest.raises(ProjectXOrderError) as exc_info:
            await async_function()

        assert str(exc_info.value) == "Async order error"

    def test_multiple_except_clauses(self):
        """Test catching specific exceptions."""
        def raise_error(error_type: str):
            if error_type == "auth":
                raise ProjectXAuthenticationError("Auth failed")
            elif error_type == "rate":
                raise ProjectXRateLimitError("Rate limited")
            else:
                raise ProjectXError("Generic error")

        # Test auth error
        try:
            raise_error("auth")
        except ProjectXAuthenticationError as e:
            assert str(e) == "Auth failed"
        except ProjectXError:
            pytest.fail("Should catch specific exception")

        # Test rate error
        try:
            raise_error("rate")
        except ProjectXRateLimitError as e:
            assert str(e) == "Rate limited"
        except ProjectXError:
            pytest.fail("Should catch specific exception")

        # Test generic error
        try:
            raise_error("other")
        except ProjectXAuthenticationError:
            pytest.fail("Should not catch this")
        except ProjectXRateLimitError:
            pytest.fail("Should not catch this")
        except ProjectXError as e:
            assert str(e) == "Generic error"


class TestExceptionSerialization:
    """Test exception serialization and pickling."""

    def test_pickle_unpickle(self):
        """Test that exceptions can be pickled and unpickled."""
        original = ProjectXOrderError(
            "Order failed",
            error_code=400,
            response_data={"order_id": "12345"}
        )

        # Pickle and unpickle
        pickled = pickle.dumps(original)
        unpickled = pickle.loads(pickled)

        assert str(unpickled) == str(original)
        assert unpickled.error_code == original.error_code
        assert unpickled.response_data == original.response_data

    def test_json_serializable_response_data(self):
        """Test that response_data can be JSON serialized."""
        data = {
            "status": "error",
            "code": 500,
            "details": ["item1", "item2"],
            "metadata": {"key": "value"}
        }
        error = ProjectXError("Test", response_data=data)

        # Should be JSON serializable
        json_str = json.dumps(error.response_data)
        assert json_str is not None

        # Should deserialize correctly
        deserialized = json.loads(json_str)
        assert deserialized == data


class TestExceptionStringRepresentation:
    """Test string representations of exceptions."""

    def test_str_representation(self):
        """Test __str__ representation."""
        error = ProjectXError("Error message")
        assert str(error) == "Error message"

    def test_repr_representation(self):
        """Test __repr__ representation."""
        error = ProjectXError("Test error", error_code=500)
        repr_str = repr(error)
        assert "ProjectXError" in repr_str
        assert "Test error" in repr_str

    def test_format_string_compatibility(self):
        """Test using exceptions in format strings."""
        error = ProjectXError("Format test")
        formatted = f"Error occurred: {error}"
        assert formatted == "Error occurred: Format test"

    def test_logging_compatibility(self):
        """Test that exceptions work with logging."""
        import logging
        from io import StringIO

        # Setup logger with string handler
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger("test_logger")
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)

        # Log the exception
        error = ProjectXConnectionError("Connection failed", error_code=502)
        logger.error("Error: %s", error)

        # Check log output
        log_output = log_stream.getvalue()
        assert "Connection failed" in log_output


class TestExceptionMemoryAndPerformance:
    """Test memory and performance aspects."""

    def test_no_memory_leak_large_response(self):
        """Test that large response data doesn't cause memory issues."""
        # Create large response data
        large_data = {f"key_{i}": f"value_{i}" * 100 for i in range(1000)}

        errors = []
        for _ in range(100):
            error = ProjectXDataError("Large data", response_data=large_data)
            errors.append(error)

        # Should not raise memory errors
        assert len(errors) == 100

        # Clear references
        errors.clear()

    def test_exception_creation_performance(self):
        """Test that exception creation is fast."""
        import time

        start_time = time.time()

        # Create many exceptions
        for _ in range(10000):
            ProjectXError("Test", error_code=500, response_data={"key": "value"})

        elapsed = time.time() - start_time

        # Should be fast (less than 1 second for 10000 exceptions)
        assert elapsed < 1.0


class TestExceptionIntegration:
    """Test exception integration with other modules."""

    def test_exception_used_correctly_in_type_hints(self):
        """Test that exceptions work with type hints."""
        def function_that_raises() -> None:
            """Function with type hints that raises exception."""
            raise ProjectXOrderError("Order failed")

        with pytest.raises(ProjectXOrderError):
            function_that_raises()

    def test_exception_hierarchy_for_catching(self):
        """Test exception hierarchy for proper catching."""
        exceptions_to_test = [
            (ProjectXAuthenticationError("Auth"), ProjectXError),
            (ProjectXRateLimitError("Rate"), ProjectXError),
            (ProjectXServerError("Server"), ProjectXError),
            (ProjectXClientError("Client"), ProjectXError),
            (InvalidOrderParameters("Invalid"), ProjectXError),  # Fixed: inherits from ProjectXError
            (RiskLimitExceeded("Risk"), ProjectXError),
        ]

        for specific_error, base_class in exceptions_to_test:
            try:
                raise specific_error
            except base_class as e:
                assert isinstance(e, base_class)

    def test_error_codes_consistency(self):
        """Test that error codes are used consistently."""
        # Common HTTP error codes
        auth_error = ProjectXAuthenticationError("Unauthorized", error_code=401)
        assert auth_error.error_code == 401

        rate_error = ProjectXRateLimitError("Too many requests", error_code=429)
        assert rate_error.error_code == 429

        server_error = ProjectXServerError("Internal error", error_code=500)
        assert server_error.error_code == 500

        client_error = ProjectXClientError("Bad request", error_code=400)
        assert client_error.error_code == 400
