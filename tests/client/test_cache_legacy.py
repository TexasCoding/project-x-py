"""Tests for the cache module of ProjectX client."""

from datetime import datetime
from unittest.mock import patch

import polars as pl
import pytest
import pytz

from project_x_py.client.cache import CacheMixin
from project_x_py.models import Instrument


class MockCacheClient(CacheMixin):
    """Mock client that includes CacheMixin for testing."""

    def __init__(self):
        # Set config before calling super().__init__()
        self.config = {"compression_threshold": 1024, "compression_level": 3}
        super().__init__()


class TestCacheMixin:
    """Test suite for CacheMixin class."""

    @pytest.fixture
    def cache_client(self):
        """Create a mock client with CacheMixin for testing."""
        return MockCacheClient()

    def test_initialization(self, cache_client):
        """Test cache initialization."""
        assert cache_client.cache_ttl == 300  # Default 5 minutes
        assert cache_client.cache_hit_count == 0
        assert cache_client.compression_threshold == 1024
        assert cache_client.compression_level == 3
        assert len(cache_client._opt_instrument_cache) == 0
        assert len(cache_client._opt_market_data_cache) == 0

    def test_cache_ttl_setter(self, cache_client):
        """Test setting cache TTL recreates caches."""
        # Add some data first
        instrument = Instrument(
            id="TEST123",
            name="TEST",
            description="Test instrument",
            tickSize=0.25,
            tickValue=12.5,
            activeContract=True,
            symbolId="TEST",
        )
        cache_client.cache_instrument("TEST", instrument)

        # Change TTL
        cache_client.cache_ttl = 600

        # Verify new TTL and caches are cleared
        assert cache_client.cache_ttl == 600
        assert cache_client._opt_instrument_cache.ttl == 600
        assert cache_client._opt_market_data_cache.ttl == 600
        # Caches should be recreated (empty)
        assert len(cache_client._opt_instrument_cache) == 0

    def test_cache_instrument(self, cache_client):
        """Test caching an instrument."""
        instrument = Instrument(
            id="CON.F.US.MNQ.U25",
            name="MNQU25",
            description="Micro E-mini Nasdaq-100",
            tickSize=0.25,
            tickValue=12.5,
            activeContract=True,
            symbolId="MNQ",
        )

        cache_client.cache_instrument("MNQ", instrument)

        assert "MNQ" in cache_client._opt_instrument_cache
        assert cache_client._opt_instrument_cache["MNQ"] == instrument

    def test_get_cached_instrument_hit(self, cache_client):
        """Test getting a cached instrument (cache hit)."""
        instrument = Instrument(
            id="CON.F.US.ES.H25",
            name="ESH25",
            description="E-mini S&P 500",
            tickSize=0.25,
            tickValue=12.5,
            activeContract=True,
            symbolId="ES",
        )

        cache_client.cache_instrument("ES", instrument)
        cache_hit_count_before = cache_client.cache_hit_count

        cached = cache_client.get_cached_instrument("ES")

        assert cached == instrument
        assert cache_client.cache_hit_count == cache_hit_count_before + 1

    def test_get_cached_instrument_miss(self, cache_client):
        """Test getting a non-cached instrument (cache miss)."""
        cached = cache_client.get_cached_instrument("UNKNOWN")

        assert cached is None
        assert cache_client.cache_hit_count == 0

    def test_get_cached_instrument_case_insensitive(self, cache_client):
        """Test that instrument cache is case-insensitive."""
        instrument = Instrument(
            id="TEST",
            name="TEST",
            description="Test",
            tickSize=1.0,
            tickValue=1.0,
            activeContract=True,
            symbolId="TEST",
        )

        cache_client.cache_instrument("test", instrument)

        # Should find it with different case
        cached = cache_client.get_cached_instrument("TEST")
        assert cached == instrument

        cached = cache_client.get_cached_instrument("TeSt")
        assert cached == instrument

    def test_serialize_dataframe_small(self, cache_client):
        """Test serializing a small DataFrame (no compression)."""
        # Create a very small DataFrame that won't exceed compression threshold
        df = pl.DataFrame({"value": [1.0]})

        serialized = cache_client._serialize_dataframe(df)

        # Check the actual size to determine if it's compressed
        # IPC format adds overhead, so even small DataFrames might be > 1KB
        if len(serialized) - 3 > cache_client.compression_threshold:
            assert serialized.startswith(b"LZ4")  # Compressed
        else:
            assert serialized.startswith(b"RAW")  # Not compressed
        assert len(serialized) > 3

    def test_serialize_dataframe_large(self, cache_client):
        """Test serializing a large DataFrame (with compression)."""
        # Create a large DataFrame that exceeds compression threshold
        df = pl.DataFrame(
            {
                "timestamp": [datetime.now(pytz.UTC)] * 100,
                "open": [100.0] * 100,
                "high": [101.0] * 100,
                "low": [99.0] * 100,
                "close": [100.5] * 100,
                "volume": [1000] * 100,
            }
        )

        serialized = cache_client._serialize_dataframe(df)

        assert serialized.startswith(b"LZ4")  # Compressed
        assert len(serialized) > 3

    def test_serialize_empty_dataframe(self, cache_client):
        """Test serializing an empty DataFrame."""
        df = pl.DataFrame()

        serialized = cache_client._serialize_dataframe(df)

        assert serialized == b""

    def test_deserialize_dataframe_small(self, cache_client):
        """Test deserializing a small DataFrame."""
        original_df = pl.DataFrame(
            {
                "timestamp": [datetime(2025, 1, 15, 10, 30, tzinfo=pytz.UTC)],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1000],
            }
        )

        serialized = cache_client._serialize_dataframe(original_df)
        deserialized = cache_client._deserialize_dataframe(serialized)

        assert deserialized is not None
        assert deserialized.equals(original_df)

    def test_deserialize_dataframe_large(self, cache_client):
        """Test deserializing a large compressed DataFrame."""
        # Create a large DataFrame
        original_df = pl.DataFrame(
            {
                "timestamp": [
                    datetime(2025, 1, 15, i, 0, tzinfo=pytz.UTC) for i in range(24)
                ],
                "open": [100.0 + i for i in range(24)],
                "high": [101.0 + i for i in range(24)],
                "low": [99.0 + i for i in range(24)],
                "close": [100.5 + i for i in range(24)],
                "volume": [1000 * i for i in range(24)],
            }
        )

        serialized = cache_client._serialize_dataframe(original_df)
        deserialized = cache_client._deserialize_dataframe(serialized)

        assert deserialized is not None
        assert len(deserialized) == len(original_df)
        assert list(deserialized.columns) == list(original_df.columns)

    def test_deserialize_empty_data(self, cache_client):
        """Test deserializing empty data."""
        deserialized = cache_client._deserialize_dataframe(b"")

        assert deserialized is None

    def test_deserialize_corrupted_lz4(self, cache_client):
        """Test deserializing corrupted LZ4 data."""
        corrupted = b"LZ4" + b"corrupted_data"

        with patch("project_x_py.client.cache.logger") as mock_logger:
            deserialized = cache_client._deserialize_dataframe(corrupted)

            assert deserialized is None
            mock_logger.warning.assert_called_once()

    def test_deserialize_unknown_header(self, cache_client):
        """Test deserializing data with unknown header."""
        unknown = b"XXX" + b"some_data"

        with patch("project_x_py.client.cache.logger") as mock_logger:
            deserialized = cache_client._deserialize_dataframe(unknown)

            assert deserialized is None
            mock_logger.warning.assert_called_once()

    def test_cache_market_data(self, cache_client):
        """Test caching market data."""
        df = pl.DataFrame(
            {"timestamp": [datetime.now(pytz.UTC)], "close": [100.0], "volume": [1000]}
        )

        cache_key = "TEST_KEY"
        cache_client.cache_market_data(cache_key, df)

        assert cache_key in cache_client._opt_market_data_cache
        assert len(cache_client._opt_market_data_cache[cache_key]) > 0

    def test_get_cached_market_data_hit(self, cache_client):
        """Test getting cached market data (cache hit)."""
        original_df = pl.DataFrame(
            {"timestamp": [datetime.now(pytz.UTC)], "close": [100.0], "volume": [1000]}
        )

        cache_key = "TEST_KEY"
        cache_client.cache_market_data(cache_key, original_df)
        cache_hit_count_before = cache_client.cache_hit_count

        cached_df = cache_client.get_cached_market_data(cache_key)

        assert cached_df is not None
        assert cached_df.equals(original_df)
        assert cache_client.cache_hit_count == cache_hit_count_before + 1

    def test_get_cached_market_data_miss(self, cache_client):
        """Test getting non-cached market data (cache miss)."""
        cached_df = cache_client.get_cached_market_data("UNKNOWN_KEY")

        assert cached_df is None
        assert cache_client.cache_hit_count == 0

    def test_get_cached_market_data_corrupted(self, cache_client):
        """Test getting market data with corrupted cache entry."""
        cache_key = "CORRUPTED"
        cache_client._opt_market_data_cache[cache_key] = b"corrupted_data"

        cached_df = cache_client.get_cached_market_data(cache_key)

        assert cached_df is None
        assert cache_client.cache_hit_count == 0

    def test_clear_all_caches(self, cache_client):
        """Test clearing all caches."""
        # Add some data
        instrument = Instrument(
            id="TEST",
            name="TEST",
            description="Test",
            tickSize=1.0,
            tickValue=1.0,
            activeContract=True,
            symbolId="TEST",
        )
        cache_client.cache_instrument("TEST", instrument)

        df = pl.DataFrame({"value": [1, 2, 3]})
        cache_client.cache_market_data("TEST_DATA", df)
        cache_client.cache_hit_count = 10

        # Clear caches
        cache_client.clear_all_caches()

        assert len(cache_client._opt_instrument_cache) == 0
        assert len(cache_client._opt_market_data_cache) == 0
        assert cache_client.cache_hit_count == 0

    def test_get_cache_stats(self, cache_client):
        """Test getting cache statistics."""
        # Add some data
        instrument = Instrument(
            id="TEST",
            name="TEST",
            description="Test",
            tickSize=1.0,
            tickValue=1.0,
            activeContract=True,
            symbolId="TEST",
        )
        cache_client.cache_instrument("TEST", instrument)

        df = pl.DataFrame({"value": [1, 2, 3]})
        cache_client.cache_market_data("TEST_DATA", df)
        cache_client.cache_hit_count = 5

        stats = cache_client.get_cache_stats()

        assert stats["cache_hits"] == 5
        assert stats["instrument_cache_size"] == 1
        assert stats["market_data_cache_size"] == 1
        assert stats["instrument_cache_max"] == 1000
        assert stats["market_data_cache_max"] == 10000
        assert stats["compression_enabled"] is True
        assert stats["serialization"] == "arrow-ipc"
        assert stats["compression"] == "lz4"

    def test_cache_ttl_expiration(self, cache_client):
        """Test that cache respects TTL expiration."""
        # Set very short TTL
        cache_client.cache_ttl = 0.001  # 1 millisecond

        instrument = Instrument(
            id="TEST",
            name="TEST",
            description="Test",
            tickSize=1.0,
            tickValue=1.0,
            activeContract=True,
            symbolId="TEST",
        )
        cache_client.cache_instrument("TEST", instrument)

        # Wait for expiration
        import time

        time.sleep(0.01)

        # Should be expired
        cached = cache_client.get_cached_instrument("TEST")
        assert cached is None
