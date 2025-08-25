"""Comprehensive tests for data_utils module."""

from datetime import datetime, timezone
from typing import Any

import polars as pl
import pytest

from project_x_py.utils.data_utils import (
    create_data_snapshot,
    get_polars_last_value,
    get_polars_rows,
)


class TestGetPolarsRows:
    """Test the get_polars_rows function."""

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pl.DataFrame()
        assert get_polars_rows(df) == 0

    def test_single_row_dataframe(self):
        """Test with single row DataFrame."""
        df = pl.DataFrame({"col1": [1]})
        assert get_polars_rows(df) == 1

    def test_multiple_rows_dataframe(self):
        """Test with multiple rows DataFrame."""
        df = pl.DataFrame({"col1": [1, 2, 3, 4, 5]})
        assert get_polars_rows(df) == 5

    def test_large_dataframe(self):
        """Test with large DataFrame."""
        df = pl.DataFrame({"col1": list(range(10000))})
        assert get_polars_rows(df) == 10000

    def test_dataframe_without_height_attribute(self):
        """Test with object that doesn't have height attribute."""
        class MockDF:
            pass

        mock_df = MockDF()
        assert get_polars_rows(mock_df) == 0

    def test_dataframe_with_multiple_columns(self):
        """Test with DataFrame having multiple columns."""
        df = pl.DataFrame({
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1100, 1200]
        })
        assert get_polars_rows(df) == 3


class TestGetPolarsLastValue:
    """Test the get_polars_last_value function."""

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pl.DataFrame({"col1": [], "col2": []}, schema={"col1": pl.Float64, "col2": pl.Int64})
        assert get_polars_last_value(df, "col1") is None

    def test_single_row_dataframe(self):
        """Test with single row DataFrame."""
        df = pl.DataFrame({"price": [100.5]})
        assert get_polars_last_value(df, "price") == 100.5

    def test_multiple_rows_dataframe(self):
        """Test with multiple rows DataFrame."""
        df = pl.DataFrame({"price": [100.0, 101.0, 102.0, 103.0]})
        assert get_polars_last_value(df, "price") == 103.0

    def test_string_column(self):
        """Test with string column."""
        df = pl.DataFrame({"symbol": ["AAPL", "MSFT", "GOOGL"]})
        assert get_polars_last_value(df, "symbol") == "GOOGL"

    def test_integer_column(self):
        """Test with integer column."""
        df = pl.DataFrame({"volume": [1000, 1100, 1200, 1300]})
        assert get_polars_last_value(df, "volume") == 1300

    def test_float_column(self):
        """Test with float column."""
        df = pl.DataFrame({"price": [100.1, 100.2, 100.3]})
        assert get_polars_last_value(df, "price") == 100.3

    def test_null_values_in_column(self):
        """Test with null values in column."""
        df = pl.DataFrame({"price": [100.0, None, 102.0]})
        assert get_polars_last_value(df, "price") == 102.0

    def test_all_null_values(self):
        """Test with all null values."""
        df = pl.DataFrame({"price": [None, None, None]})
        assert get_polars_last_value(df, "price") is None

    def test_boolean_column(self):
        """Test with boolean column."""
        df = pl.DataFrame({"flag": [True, False, True]})
        assert get_polars_last_value(df, "flag") is True

    def test_datetime_column(self):
        """Test with datetime column."""
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3)
        ]
        df = pl.DataFrame({"timestamp": dates})
        assert get_polars_last_value(df, "timestamp") == datetime(2024, 1, 3)

    def test_nonexistent_column(self):
        """Test with non-existent column."""
        df = pl.DataFrame({"price": [100.0, 101.0]})
        with pytest.raises(pl.exceptions.ColumnNotFoundError):
            get_polars_last_value(df, "nonexistent")


class TestCreateDataSnapshot:
    """Test the create_data_snapshot function."""

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pl.DataFrame()
        snapshot = create_data_snapshot(df, "Empty test data")

        assert snapshot["description"] == "Empty test data"
        assert snapshot["row_count"] == 0
        assert snapshot["columns"] == []
        assert snapshot["empty"] is True

    def test_basic_numeric_dataframe(self):
        """Test with basic numeric DataFrame."""
        df = pl.DataFrame({
            "price": [100.0, 101.0, 102.0],
            "volume": [1000, 1100, 1200]
        })
        snapshot = create_data_snapshot(df, "Basic numeric data")

        assert snapshot["description"] == "Basic numeric data"
        assert snapshot["row_count"] == 3
        assert snapshot["columns"] == ["price", "volume"]
        assert snapshot["empty"] is False
        assert "dtypes" in snapshot
        assert "created_at" in snapshot
        assert "statistics" in snapshot

    def test_ohlcv_dataframe(self):
        """Test with OHLCV DataFrame."""
        df = pl.DataFrame({
            "timestamp": [
                datetime(2024, 1, 1, 9, 0),
                datetime(2024, 1, 1, 9, 1),
                datetime(2024, 1, 1, 9, 2)
            ],
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1100, 1200]
        })
        snapshot = create_data_snapshot(df, "OHLCV data")

        assert snapshot["description"] == "OHLCV data"
        assert snapshot["row_count"] == 3
        assert snapshot["empty"] is False
        assert "time_range" in snapshot
        assert "timespan" in snapshot
        assert snapshot["time_range"]["start"] == datetime(2024, 1, 1, 9, 0)
        assert snapshot["time_range"]["end"] == datetime(2024, 1, 1, 9, 2)
        assert snapshot["timespan"] == 120.0  # 2 minutes in seconds

    def test_mixed_data_types(self):
        """Test with mixed data types."""
        df = pl.DataFrame({
            "symbol": ["AAPL", "MSFT", "GOOGL"],
            "price": [150.0, 300.0, 2500.0],
            "volume": [1000000, 800000, 500000],
            "active": [True, True, False]
        })
        snapshot = create_data_snapshot(df, "Mixed data types")

        assert snapshot["row_count"] == 3
        assert len(snapshot["columns"]) == 4
        assert "dtypes" in snapshot
        assert "statistics" in snapshot
        # Only numeric columns should have statistics
        assert "price" in snapshot["statistics"]
        assert "volume" in snapshot["statistics"]
        assert "symbol" not in snapshot["statistics"]

    def test_statistics_calculation(self):
        """Test statistics calculation for numeric columns."""
        df = pl.DataFrame({
            "price": [100.0, 150.0, 200.0, 125.0, 175.0],
            "volume": [1000, 2000, 3000, 1500, 2500]
        })
        snapshot = create_data_snapshot(df, "Statistics test")

        stats = snapshot["statistics"]
        assert "price" in stats
        assert "volume" in stats

        # Check price statistics
        price_stats = stats["price"]
        assert price_stats["min"] == 100.0
        assert price_stats["max"] == 200.0
        assert price_stats["mean"] == 150.0
        assert "std" in price_stats

        # Check volume statistics
        volume_stats = stats["volume"]
        assert volume_stats["min"] == 1000
        assert volume_stats["max"] == 3000
        assert volume_stats["mean"] == 2000.0

    def test_time_column_detection(self):
        """Test detection of time columns."""
        df = pl.DataFrame({
            "custom_time": [
                datetime(2024, 1, 1, 10, 0),
                datetime(2024, 1, 1, 10, 5)
            ],
            "price": [100.0, 101.0]
        })
        snapshot = create_data_snapshot(df, "Custom time column")

        assert "time_range" in snapshot
        assert snapshot["time_range"]["start"] == datetime(2024, 1, 1, 10, 0)
        assert snapshot["time_range"]["end"] == datetime(2024, 1, 1, 10, 5)
        assert snapshot["timespan"] == 300.0  # 5 minutes

    def test_time_column_with_timezone(self):
        """Test time column with timezone information."""
        tz = timezone.utc
        df = pl.DataFrame({
            "timestamp": [
                datetime(2024, 1, 1, 10, 0, tzinfo=tz),
                datetime(2024, 1, 1, 10, 5, tzinfo=tz)
            ],
            "price": [100.0, 101.0]
        })
        snapshot = create_data_snapshot(df, "Timezone test")

        assert "time_range" in snapshot
        assert "timespan" in snapshot

    def test_no_timestamp_column(self):
        """Test DataFrame without timestamp column."""
        df = pl.DataFrame({
            "price": [100.0, 101.0, 102.0],
            "volume": [1000, 1100, 1200]
        })
        snapshot = create_data_snapshot(df, "No timestamp")

        assert "time_range" not in snapshot
        assert "timespan" not in snapshot

    def test_malformed_statistics_handling(self):
        """Test handling of errors in statistics calculation."""
        # Create a DataFrame that might cause statistics calculation errors
        df = pl.DataFrame({
            "price": [float('inf'), 100.0, float('-inf')],
            "volume": [1000, None, 2000]
        })
        snapshot = create_data_snapshot(df, "Malformed data")

        assert "statistics" in snapshot
        # Should handle errors gracefully

    def test_default_description(self):
        """Test with default empty description."""
        df = pl.DataFrame({"price": [100.0]})
        snapshot = create_data_snapshot(df)

        assert snapshot["description"] == ""

    def test_single_row_dataframe(self):
        """Test with single row DataFrame."""
        df = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 1, 10, 0)],
            "price": [100.0],
            "volume": [1000]
        })
        snapshot = create_data_snapshot(df, "Single row")

        assert snapshot["row_count"] == 1
        assert "time_range" in snapshot
        assert snapshot["time_range"]["start"] == datetime(2024, 1, 1, 10, 0)
        assert snapshot["time_range"]["end"] == datetime(2024, 1, 1, 10, 0)
        assert snapshot["timespan"] == 0.0

    def test_large_dataframe_performance(self):
        """Test performance with large DataFrame."""
        # Create a large DataFrame to test performance
        size = 1000  # Reduced size to avoid minute overflow
        df = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 1, 10, i % 60, i // 60) for i in range(size)],
            "price": [100.0 + i * 0.01 for i in range(size)],
            "volume": [1000 + i for i in range(size)]
        })

        # This should complete without timeout
        snapshot = create_data_snapshot(df, "Large dataset")

        assert snapshot["row_count"] == size
        assert "statistics" in snapshot
        assert "time_range" in snapshot

    def test_numeric_column_types(self):
        """Test different numeric column types."""
        df = pl.DataFrame({
            "int32_col": [1, 2, 3],
            "int64_col": [100, 200, 300],
            "float32_col": [1.1, 2.2, 3.3],
            "float64_col": [10.1, 20.2, 30.3],
            "string_col": ["a", "b", "c"]
        }).with_columns([
            pl.col("int32_col").cast(pl.Int32),
            pl.col("int64_col").cast(pl.Int64),
            pl.col("float32_col").cast(pl.Float32),
            pl.col("float64_col").cast(pl.Float64)
        ])

        snapshot = create_data_snapshot(df, "Numeric types test")

        stats = snapshot["statistics"]
        assert "int32_col" in stats
        assert "int64_col" in stats
        assert "float32_col" in stats
        assert "float64_col" in stats
        assert "string_col" not in stats

    def test_invalid_time_column_handling(self):
        """Test handling of invalid time column data."""
        df = pl.DataFrame({
            "timestamp": ["invalid", "date", "values"],
            "price": [100.0, 101.0, 102.0]
        })

        # Should not raise an exception
        snapshot = create_data_snapshot(df, "Invalid time data")

        # Should have time_range with the invalid string values
        # The function treats them as valid timestamps and returns first/last
        assert "time_range" in snapshot
        assert snapshot["row_count"] == 3

    def test_created_at_timestamp(self):
        """Test that created_at timestamp is set correctly."""
        df = pl.DataFrame({"price": [100.0]})
        before = datetime.now()
        snapshot = create_data_snapshot(df, "Timestamp test")
        after = datetime.now()

        created_at = snapshot["created_at"]
        assert isinstance(created_at, datetime)
        assert before <= created_at <= after

    def test_dtypes_mapping(self):
        """Test that dtypes are correctly mapped to strings."""
        df = pl.DataFrame({
            "int_col": [1, 2, 3],
            "float_col": [1.1, 2.2, 3.3],
            "str_col": ["a", "b", "c"],
            "bool_col": [True, False, True]
        })

        snapshot = create_data_snapshot(df, "Dtypes test")

        dtypes = snapshot["dtypes"]
        assert all(isinstance(dtype, str) for dtype in dtypes.values())
        assert len(dtypes) == 4
