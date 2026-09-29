"""
Optimized caching with Arrow IPC serialization and lz4 compression for ProjectX.

This module provides a high-performance caching layer (`CacheMixin`) designed to
significantly reduce latency and memory usage for the ProjectX async client. It
uses the robust and efficient Arrow IPC format for serialization.

Key Features:
- Arrow IPC: For fast, robust, and type-preserving serialization of DataFrames.
- lz4: For high-speed data compression, achieving up to 70% size reduction on market data.
- cachetools: Implements intelligent TTL (Time-to-Live) cache eviction policies for
  both instruments and market data.
- Automatic Compression: Data payloads exceeding a configurable threshold (default 1KB)
  are automatically compressed.
- Performance-Tuned: Optimized for handling Polars DataFrames and other data models
  used within the SDK.
"""

import gc
import io
import logging
from typing import Any

import lz4.frame
import polars as pl
from cachetools import TTLCache

from project_x_py.models import Instrument

logger = logging.getLogger(__name__)


class CacheMixin:
    """
    High-performance caching with Arrow IPC serialization and lz4 compression.

    This optimized cache provides:
    - Fast, robust serialization with Arrow IPC format
    - 70% memory reduction with lz4 compression
    - TTL cache for instruments and market data with automatic time-based eviction
    - Compression for large data (> 1KB)
    - Performance metrics and statistics
    """

    def __init__(self) -> None:
        """Initialize optimized caches."""
        super().__init__()

        # Cache settings (set early so they can be overridden)
        self._cache_ttl: float = 300.0  # 5 minutes default
        self.cache_hit_count = 0

        # Internal optimized caches with time-to-live eviction
        self._opt_instrument_cache: TTLCache[str, Instrument] = TTLCache(
            maxsize=1000, ttl=self._cache_ttl
        )
        self._opt_market_data_cache: TTLCache[str, bytes] = TTLCache(
            maxsize=10000, ttl=self._cache_ttl
        )

        # Compression settings (configurable)
        self.compression_threshold = getattr(self, "config", {}).get(
            "compression_threshold", 1024
        )  # Compress data > 1KB
        self.compression_level = getattr(self, "config", {}).get(
            "compression_level", 3
        )  # lz4 compression level (0-16)

    @property
    def cache_ttl(self) -> float:
        """Get cache TTL value."""
        return self._cache_ttl

    @cache_ttl.setter
    def cache_ttl(self, value: float) -> None:
        """
        Set cache TTL and recreate caches with new TTL.

        Args:
            value: New TTL value in seconds
        """
        self._cache_ttl = value
        # Recreate caches with new TTL
        self._opt_instrument_cache = TTLCache[str, Instrument](maxsize=1000, ttl=value)
        self._opt_market_data_cache = TTLCache[str, bytes](maxsize=10000, ttl=value)

    def _serialize_dataframe(self, df: pl.DataFrame) -> bytes:
        """
        Serialize Polars DataFrame efficiently using the Arrow IPC format.

        This method is significantly more robust and performant than the previous
        msgpack-based serialization. It preserves all data types, including
        timezones, without manual conversion.

        Args:
            df: The Polars DataFrame to serialize.

        Returns:
            The serialized DataFrame as bytes, potentially compressed.
        """
        if df.is_empty():
            return b""

        # Use Polars' built-in IPC serialization
        buffer = io.BytesIO()
        df.write_ipc(buffer)
        packed = buffer.getvalue()

        # Compress if data is large
        if len(packed) > self.compression_threshold:
            compressed: bytes = lz4.frame.compress(
                packed,
                compression_level=self.compression_level,
                content_checksum=False,  # Skip checksum for speed
            )
            # Add header to indicate compression
            return b"LZ4" + compressed

        return b"RAW" + packed

    def _deserialize_dataframe(self, data: bytes) -> pl.DataFrame | None:
        """
        Deserialize DataFrame from cached bytes using the Arrow IPC format.

        This method correctly handles data serialized by `_serialize_dataframe`,
        including decompression and type reconstruction.

        Args:
            data: The byte string from the cache.

        Returns:
            A deserialized Polars DataFrame, or None if deserialization fails.
        """
        if not data:
            return None

        # Check header for compression
        header = data[:3]
        payload = data[3:]

        # Decompress if needed
        if header == b"LZ4":
            try:
                payload = lz4.frame.decompress(payload)
            except Exception as e:
                logger.warning(f"LZ4 decompression failed for cached data: {e}")
                return None  # Data is corrupt, cannot proceed
        elif header != b"RAW":
            logger.warning(
                f"Unknown cache format header '{header.decode(errors='ignore')}'. "
                "Cache may be from an old version. Clearing and refetching is recommended."
            )
            return None

        try:
            # Use Polars' built-in IPC deserialization
            buffer = io.BytesIO(payload)
            return pl.read_ipc(buffer)
        except Exception as e:
            logger.debug(f"Failed to deserialize DataFrame from IPC format: {e}")
            return None

    def get_cached_instrument(self, symbol: str) -> Instrument | None:
        """
        Get cached instrument data if available and not expired.

        Args:
            symbol: Trading symbol

        Returns:
            Cached instrument or None if not found or expired.
        """
        cache_key = symbol.upper()
        instrument = self._opt_instrument_cache.get(cache_key)
        if instrument:
            self.cache_hit_count += 1
            return instrument
        return None

    def cache_instrument(self, symbol: str, instrument: Instrument) -> None:
        """
        Cache instrument data with a time-to-live.

        Args:
            symbol: Trading symbol
            instrument: Instrument object to cache
        """
        cache_key = symbol.upper()
        self._opt_instrument_cache[cache_key] = instrument

    def get_cached_market_data(self, cache_key: str) -> pl.DataFrame | None:
        """
        Get cached market data if available and not expired.

        Args:
            cache_key: Unique key for the cached data

        Returns:
            Cached DataFrame or None if not found or expired.
        """
        serialized = self._opt_market_data_cache.get(cache_key)
        if serialized:
            df = self._deserialize_dataframe(serialized)
            if df is not None:
                self.cache_hit_count += 1
                return df
        return None

    def cache_market_data(self, cache_key: str, data: pl.DataFrame) -> None:
        """
        Cache market data with a time-to-live.

        Args:
            cache_key: Unique key for the data
            data: DataFrame to cache
        """
        serialized = self._serialize_dataframe(data)
        self._opt_market_data_cache[cache_key] = serialized

    def clear_all_caches(self) -> None:
        """
        Clear all cached data.
        """
        self._opt_instrument_cache.clear()
        self._opt_market_data_cache.clear()
        self.cache_hit_count = 0
        gc.collect()

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get comprehensive cache statistics.
        """
        total_hits = self.cache_hit_count

        return {
            "cache_hits": total_hits,
            "instrument_cache_size": len(self._opt_instrument_cache),
            "market_data_cache_size": len(self._opt_market_data_cache),
            "instrument_cache_max": self._opt_instrument_cache.maxsize,
            "market_data_cache_max": self._opt_market_data_cache.maxsize,
            "compression_enabled": True,
            "serialization": "arrow-ipc",
            "compression": "lz4",
        }
