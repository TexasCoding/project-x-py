"""Tests for memory-mapped storage functionality."""

import tempfile
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from project_x_py.data import MemoryMappedStorage, TimeSeriesStorage


class TestMemoryMappedStorage:
    """Tests for MemoryMappedStorage class."""

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)
        yield temp_path
        # Cleanup
        temp_path.unlink(missing_ok=True)
        meta_path = temp_path.with_suffix(".meta")
        meta_path.unlink(missing_ok=True)

    def test_write_read_array(self, temp_file):
        """Test writing and reading NumPy arrays."""
        with MemoryMappedStorage(temp_file) as storage:
            # Create test array
            test_array = np.array([1, 2, 3, 4, 5], dtype=np.float64)

            # Write array
            bytes_written = storage.write_array(test_array)
            assert bytes_written > 0

            # Read array back
            read_array = storage.read_array()
            assert read_array is not None
            np.testing.assert_array_equal(read_array, test_array)

    def test_write_read_dataframe(self, temp_file):
        """Test writing and reading Polars DataFrames."""
        with MemoryMappedStorage(temp_file) as storage:
            # Create test DataFrame
            test_df = pl.DataFrame(
                {
                    "price": [100.0, 101.0, 102.0],
                    "volume": [1000, 2000, 1500],
                    "timestamp": [1, 2, 3],
                }
            )

            # Write DataFrame
            success = storage.write_dataframe(test_df, key="test")
            assert success

            # Read DataFrame back
            read_df = storage.read_dataframe(key="test")
            assert read_df is not None
            assert read_df.shape == test_df.shape
            assert read_df.equals(test_df)

    def test_multiple_dataframes(self, temp_file):
        """Test storing multiple DataFrames with different keys."""
        with MemoryMappedStorage(temp_file) as storage:
            # Create multiple DataFrames
            df1 = pl.DataFrame({"a": [1, 2, 3]})
            df2 = pl.DataFrame({"b": [4, 5, 6]})

            # Write both
            assert storage.write_dataframe(df1, key="first")
            assert storage.write_dataframe(df2, key="second")

            # Read both back
            read_df1 = storage.read_dataframe(key="first")
            read_df2 = storage.read_dataframe(key="second")

            assert read_df1 is not None and read_df1.equals(df1)
            assert read_df2 is not None and read_df2.equals(df2)

    def test_get_info(self, temp_file):
        """Test getting storage information."""
        with MemoryMappedStorage(temp_file) as storage:
            # Write some data
            test_array = np.array([1, 2, 3, 4, 5])
            storage.write_array(test_array)

            # Get info
            info = storage.get_info()
            assert "filename" in info
            assert "exists" in info
            assert "size_mb" in info
            assert info["exists"] is True
            assert info["size_mb"] > 0

    def test_context_manager(self, temp_file):
        """Test context manager functionality."""
        # Write data
        with MemoryMappedStorage(temp_file) as storage:
            test_array = np.array([10, 20, 30])
            storage.write_array(test_array)

        # Read data in new context
        with MemoryMappedStorage(temp_file, mode="rb") as storage:
            read_array = storage.read_array()
            assert read_array is not None
            np.testing.assert_array_equal(read_array, test_array)


class TestTimeSeriesStorage:
    """Tests for TimeSeriesStorage class."""

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)
        yield temp_path
        # Cleanup
        temp_path.unlink(missing_ok=True)
        meta_path = temp_path.with_suffix(".meta")
        meta_path.unlink(missing_ok=True)

    def test_append_data(self, temp_file):
        """Test appending time series data."""
        storage = TimeSeriesStorage(temp_file, columns=["price", "volume"])

        # Append multiple data points
        assert storage.append_data(1000.0, {"price": 100.0, "volume": 1000})
        assert storage.append_data(1001.0, {"price": 101.0, "volume": 2000})
        assert storage.append_data(1002.0, {"price": 102.0, "volume": 1500})

        assert storage.current_size == 3
        storage.close()

    def test_read_window(self, temp_file):
        """Test reading data within a time window."""
        storage = TimeSeriesStorage(temp_file, columns=["price", "volume"])

        # Add test data
        for i in range(10):
            timestamp = 1000.0 + i
            storage.append_data(
                timestamp, {"price": 100.0 + i, "volume": 1000 + i * 100}
            )

        # Read window
        df = storage.read_window(1002.0, 1007.0)
        assert df is not None
        assert len(df) == 6  # timestamps 1002-1007 inclusive

        # Check first and last values
        assert df["timestamp"][0] == 1002.0
        assert df["timestamp"][-1] == 1007.0
        assert df["price"][0] == 102.0
        assert df["volume"][-1] == 1700

        storage.close()

    def test_empty_window(self, temp_file):
        """Test reading an empty time window."""
        storage = TimeSeriesStorage(temp_file, columns=["price", "volume"])

        # Add test data
        storage.append_data(1000.0, {"price": 100.0, "volume": 1000})

        # Read window with no data
        df = storage.read_window(2000.0, 3000.0)
        assert df is None

        storage.close()

    def test_partial_data(self, temp_file):
        """Test appending partial data (missing columns)."""
        storage = TimeSeriesStorage(
            temp_file, columns=["price", "volume", "bid", "ask"]
        )

        # Append with missing columns (should use 0)
        assert storage.append_data(1000.0, {"price": 100.0, "volume": 1000})
        assert storage.append_data(1001.0, {"price": 101.0, "bid": 100.5, "ask": 101.5})

        # Read back
        df = storage.read_window(999.0, 1002.0)
        assert df is not None
        assert len(df) == 2

        # Check that missing values are 0
        assert df["bid"][0] == 0.0
        assert df["ask"][0] == 0.0
        assert df["volume"][1] == 0.0

        storage.close()
