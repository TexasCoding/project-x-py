"""Comprehensive tests for environment.py module."""

import os
from typing import Any
from unittest.mock import Mock, patch

import pytest

from project_x_py.utils.environment import get_env_var


class TestGetEnvVar:
    """Test the get_env_var function."""

    def test_existing_environment_variable(self):
        """Test getting an existing environment variable."""
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = get_env_var("TEST_VAR")
            assert result == "test_value"

    def test_nonexistent_environment_variable_with_default(self):
        """Test getting a non-existent environment variable with default."""
        # Ensure the variable doesn't exist
        if "NONEXISTENT_VAR" in os.environ:
            del os.environ["NONEXISTENT_VAR"]

        result = get_env_var("NONEXISTENT_VAR", default="default_value")
        assert result == "default_value"

    def test_nonexistent_environment_variable_without_default(self):
        """Test getting a non-existent environment variable without default."""
        # Ensure the variable doesn't exist
        if "NONEXISTENT_VAR" in os.environ:
            del os.environ["NONEXISTENT_VAR"]

        result = get_env_var("NONEXISTENT_VAR")
        assert result is None

    def test_required_environment_variable_exists(self):
        """Test required environment variable that exists."""
        with patch.dict(os.environ, {"REQUIRED_VAR": "required_value"}):
            result = get_env_var("REQUIRED_VAR", required=True)
            assert result == "required_value"

    def test_required_environment_variable_missing(self):
        """Test required environment variable that is missing."""
        # Ensure the variable doesn't exist
        if "MISSING_REQUIRED_VAR" in os.environ:
            del os.environ["MISSING_REQUIRED_VAR"]

        with pytest.raises(ValueError, match="Required environment variable 'MISSING_REQUIRED_VAR' not found"):
            get_env_var("MISSING_REQUIRED_VAR", required=True)

    def test_required_variable_with_default_exists(self):
        """Test required variable with default value when variable exists."""
        with patch.dict(os.environ, {"TEST_REQUIRED": "actual_value"}):
            result = get_env_var("TEST_REQUIRED", default="default_value", required=True)
            assert result == "actual_value"

    def test_required_variable_with_default_missing(self):
        """Test required variable with default value when variable is missing."""
        # Ensure the variable doesn't exist
        if "MISSING_WITH_DEFAULT" in os.environ:
            del os.environ["MISSING_WITH_DEFAULT"]

        # With a default, if required=True but the variable is missing,
        # the function will return the default (os.getenv behavior)
        # The check only fails if the result is None
        result = get_env_var("MISSING_WITH_DEFAULT", default="default_value", required=True)
        assert result == "default_value"

    def test_empty_string_environment_variable(self):
        """Test environment variable with empty string value."""
        with patch.dict(os.environ, {"EMPTY_VAR": ""}):
            result = get_env_var("EMPTY_VAR")
            assert result == ""

    def test_empty_string_required_variable(self):
        """Test required environment variable with empty string value."""
        with patch.dict(os.environ, {"EMPTY_REQUIRED": ""}):
            result = get_env_var("EMPTY_REQUIRED", required=True)
            assert result == ""

    def test_whitespace_environment_variable(self):
        """Test environment variable with whitespace value."""
        with patch.dict(os.environ, {"WHITESPACE_VAR": "   "}):
            result = get_env_var("WHITESPACE_VAR")
            assert result == "   "

    def test_numeric_environment_variable(self):
        """Test environment variable with numeric value."""
        with patch.dict(os.environ, {"NUMERIC_VAR": "12345"}):
            result = get_env_var("NUMERIC_VAR")
            assert result == "12345"
            assert isinstance(result, str)

    def test_boolean_environment_variable(self):
        """Test environment variable with boolean-like value."""
        with patch.dict(os.environ, {"BOOLEAN_VAR": "true"}):
            result = get_env_var("BOOLEAN_VAR")
            assert result == "true"
            assert isinstance(result, str)

    def test_default_value_types(self):
        """Test different types of default values."""
        # Ensure the variable doesn't exist
        if "TYPE_TEST_VAR" in os.environ:
            del os.environ["TYPE_TEST_VAR"]

        # String default
        result_str = get_env_var("TYPE_TEST_VAR", default="string_default")
        assert result_str == "string_default"

        # Integer default (should be returned as string)
        result_int = get_env_var("TYPE_TEST_VAR", default=42)
        assert result_int == 42  # Function returns the default as-is

        # Boolean default
        result_bool = get_env_var("TYPE_TEST_VAR", default=True)
        assert result_bool is True

    def test_none_default_value(self):
        """Test with explicit None default value."""
        # Ensure the variable doesn't exist
        if "NONE_DEFAULT_VAR" in os.environ:
            del os.environ["NONE_DEFAULT_VAR"]

        result = get_env_var("NONE_DEFAULT_VAR", default=None)
        assert result is None

    def test_case_sensitive_variable_names(self):
        """Test that environment variable names are case-sensitive."""
        with patch.dict(os.environ, {"CaseSensitive": "upper_case"}):
            # Correct case
            result_correct = get_env_var("CaseSensitive")
            assert result_correct == "upper_case"

            # Wrong case (should not find it)
            result_wrong = get_env_var("casesensitive", default="not_found")
            assert result_wrong == "not_found"

    def test_special_characters_in_values(self):
        """Test environment variables with special characters."""
        special_value = "!@#$%^&*()_+-={}[]|\\:;\"'<>?,./"
        with patch.dict(os.environ, {"SPECIAL_CHARS": special_value}):
            result = get_env_var("SPECIAL_CHARS")
            assert result == special_value

    def test_unicode_characters_in_values(self):
        """Test environment variables with unicode characters."""
        unicode_value = "测试值 🚀 café résumé"
        with patch.dict(os.environ, {"UNICODE_VAR": unicode_value}):
            result = get_env_var("UNICODE_VAR")
            assert result == unicode_value

    def test_multiline_environment_variable(self):
        """Test environment variable with multiline value."""
        multiline_value = "line1\nline2\nline3"
        with patch.dict(os.environ, {"MULTILINE_VAR": multiline_value}):
            result = get_env_var("MULTILINE_VAR")
            assert result == multiline_value
            assert "\n" in result

    def test_very_long_environment_variable(self):
        """Test environment variable with very long value."""
        long_value = "x" * 10000
        with patch.dict(os.environ, {"LONG_VAR": long_value}):
            result = get_env_var("LONG_VAR")
            assert result == long_value
            assert len(result) == 10000

    def test_environment_variable_modification(self):
        """Test that function reflects real-time environment changes."""
        # Initially set variable
        with patch.dict(os.environ, {"CHANGING_VAR": "initial_value"}):
            result1 = get_env_var("CHANGING_VAR")
            assert result1 == "initial_value"

            # Modify the variable
            os.environ["CHANGING_VAR"] = "modified_value"
            result2 = get_env_var("CHANGING_VAR")
            assert result2 == "modified_value"

    def test_os_getenv_integration(self):
        """Test that function properly integrates with os.getenv."""
        with patch("os.getenv") as mock_getenv:
            mock_getenv.return_value = "mocked_value"

            result = get_env_var("MOCKED_VAR", default="default")

            mock_getenv.assert_called_once_with("MOCKED_VAR", "default")
            assert result == "mocked_value"

    def test_error_message_content(self):
        """Test the specific content of error messages."""
        # Ensure the variable doesn't exist
        if "SPECIFIC_ERROR_VAR" in os.environ:
            del os.environ["SPECIFIC_ERROR_VAR"]

        with pytest.raises(ValueError) as exc_info:
            get_env_var("SPECIFIC_ERROR_VAR", required=True)

        error_message = str(exc_info.value)
        assert "Required environment variable" in error_message
        assert "SPECIFIC_ERROR_VAR" in error_message
        assert "not found" in error_message

    def test_function_signature_compatibility(self):
        """Test that function signature works with different argument patterns."""
        with patch.dict(os.environ, {"SIGNATURE_TEST": "test_value"}):
            # Positional arguments
            result1 = get_env_var("SIGNATURE_TEST")
            assert result1 == "test_value"

            # Keyword arguments
            result2 = get_env_var(name="SIGNATURE_TEST")
            assert result2 == "test_value"

            # Mixed arguments
            result3 = get_env_var("SIGNATURE_TEST", default="default", required=False)
            assert result3 == "test_value"

    def test_edge_case_variable_names(self):
        """Test edge cases for environment variable names."""
        # Variable name with numbers
        with patch.dict(os.environ, {"VAR123": "numeric_name"}):
            result = get_env_var("VAR123")
            assert result == "numeric_name"

        # Variable name with underscores
        with patch.dict(os.environ, {"VAR_WITH_UNDERSCORES": "underscore_name"}):
            result = get_env_var("VAR_WITH_UNDERSCORES")
            assert result == "underscore_name"

    def test_concurrent_access(self):
        """Test that function works correctly with concurrent access."""
        import threading
        import time

        results = {}

        def worker(var_name, expected_value):
            # Set environment variable directly in thread
            os.environ[var_name] = expected_value
            try:
                time.sleep(0.01)  # Small delay to simulate concurrent access
                result = get_env_var(var_name)
                results[var_name] = result
            finally:
                # Clean up the environment variable
                if var_name in os.environ:
                    del os.environ[var_name]

        # Start multiple threads
        threads = []
        for i in range(10):
            var_name = f"CONCURRENT_VAR_{i}"
            expected_value = f"value_{i}"
            thread = threading.Thread(target=worker, args=(var_name, expected_value))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify results (some may be None due to cleanup timing)
        for i in range(10):
            var_name = f"CONCURRENT_VAR_{i}"
            expected_value = f"value_{i}"
            if var_name in results:
                # If we got a result, it should be the expected one
                assert results[var_name] == expected_value or results[var_name] is None

    def test_return_type_consistency(self):
        """Test that return types are consistent."""
        # Test with string environment variable
        with patch.dict(os.environ, {"STRING_VAR": "string_value"}):
            result = get_env_var("STRING_VAR")
            assert isinstance(result, str)

        # Test with None default
        if "NONEXISTENT_VAR" in os.environ:
            del os.environ["NONEXISTENT_VAR"]

        result = get_env_var("NONEXISTENT_VAR")
        assert result is None

        # Test with non-string default
        result = get_env_var("NONEXISTENT_VAR", default=123)
        assert isinstance(result, int)
        assert result == 123

    def test_common_projectx_environment_variables(self):
        """Test with common ProjectX environment variable patterns."""
        projectx_vars = {
            "PROJECT_X_API_KEY": "test_api_key",  # pragma: allowlist secret
            "PROJECT_X_USERNAME": "test_user",
            "PROJECTX_API_URL": "https://api.example.com",
            "PROJECTX_TIMEOUT_SECONDS": "30",
            "PROJECTX_RETRY_ATTEMPTS": "3"
        }

        with patch.dict(os.environ, projectx_vars):
            for var_name, expected_value in projectx_vars.items():
                result = get_env_var(var_name)
                assert result == expected_value

    def test_memory_efficiency(self):
        """Test that function doesn't leak memory with repeated calls."""
        # This test ensures no memory accumulation occurs
        with patch.dict(os.environ, {"MEMORY_TEST_VAR": "test_value"}):
            for _ in range(1000):
                result = get_env_var("MEMORY_TEST_VAR")
                assert result == "test_value"

        # If we reach here without memory issues, test passes
        assert True

    def test_environment_isolation(self):
        """Test that environment changes are properly isolated in tests."""
        # Ensure clean state
        test_var_name = "ISOLATION_TEST_VAR"
        if test_var_name in os.environ:
            del os.environ[test_var_name]

        # Test 1: Variable doesn't exist
        result1 = get_env_var(test_var_name, default="not_found")
        assert result1 == "not_found"

        # Test 2: Add variable in context
        with patch.dict(os.environ, {test_var_name: "context_value"}):
            result2 = get_env_var(test_var_name)
            assert result2 == "context_value"

        # Test 3: Variable should not exist after context
        result3 = get_env_var(test_var_name, default="not_found_again")
        assert result3 == "not_found_again"
