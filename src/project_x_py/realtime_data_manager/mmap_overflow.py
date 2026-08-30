"""
Memory-mapped overflow storage for real-time data manager.

This module provides overflow storage to disk using memory-mapped files
when in-memory limits are reached, preventing memory exhaustion while
maintaining fast access to recent data.
"""

import tempfile
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from project_x_py.data import MemoryMappedStorage
from project_x_py.utils import ProjectXLogger

if TYPE_CHECKING:
    from asyncio import Lock

    from project_x_py.utils.lock_optimization import AsyncRWLock

logger = ProjectXLogger.get_logger(__name__)


class MMapOverflowMixin:
    """
    Mixin for memory-mapped overflow storage in RealtimeDataManager.

    This mixin provides automatic overflow to disk when memory limits are reached,
    maintaining hot data in RAM while archiving older data to memory-mapped files.
    """

    # Type hints for attributes provided by the main class
    if TYPE_CHECKING:
        data: dict[str, pl.DataFrame]
        max_bars_per_timeframe: int
        memory_stats: dict[str, Any]
        instrument: str
        data_lock: Lock
        data_rw_lock: AsyncRWLock

    def __init__(self) -> None:
        """Initialize memory-mapped overflow storage."""
        # Note: Commenting out super().__init__() to avoid MRO issues with BaseStatisticsTracker
        # super().__init__()

        # Storage configuration (can be overridden via config)
        self.enable_mmap_overflow = getattr(self, "config", {}).get(
            "enable_mmap_overflow", True
        )
        self.overflow_threshold = getattr(self, "config", {}).get(
            "overflow_threshold", 0.8
        )  # Start overflow at 80% of max bars

        # Validate and create storage path
        base_path = getattr(self, "config", {}).get(
            "mmap_storage_path", Path.home() / ".projectx" / "data_overflow"
        )
        self.mmap_storage_path = Path(base_path)

        # Validate and create storage path
        try:
            # Check for directory traversal patterns in the original path before resolving
            original_path_str = str(base_path)
            has_traversal = any(
                suspicious in original_path_str for suspicious in ["../", "..\\", "~"]
            )

            if has_traversal:
                raise ValueError(f"Directory traversal detected in path: {base_path}")

            self.mmap_storage_path = self.mmap_storage_path.resolve()

            # Additional security check - ensure resolved path is in safe locations
            path_str = str(self.mmap_storage_path)
            home_str = str(Path.home())
            # Include the resolved system temp directory so platform symlink
            # resolution is honored (e.g. macOS resolves /tmp -> /private/tmp),
            # plus /var/folders and /private/var/folders for macOS temp dirs.
            temp_dirs = [
                str(Path(tempfile.gettempdir()).resolve()),
                "/tmp",  # nosec B108 - needed for temp file validation
                "/private/tmp",  # nosec B108 - macOS resolves /tmp here
                "/var/folders",
                "/private/var/folders",
                str(Path.cwd()),
            ]

            is_safe_path = path_str.startswith(home_str) or any(
                path_str.startswith(temp_dir) for temp_dir in temp_dirs
            )

            if not is_safe_path:
                raise ValueError(
                    f"Potentially unsafe storage path: {self.mmap_storage_path}"
                )

            # Create directory with appropriate permissions
            self.mmap_storage_path.mkdir(parents=True, exist_ok=True, mode=0o700)

        except ValueError as e:
            # For security errors with traversal attempts, re-raise
            if "traversal" in str(e):
                raise
            # For other invalid paths (unsafe or non-existent), disable overflow
            logger.error(f"Invalid overflow storage path, disabling overflow: {e}")
            self.enable_mmap_overflow = False
        except Exception as e:
            logger.error(f"Failed to create overflow storage directory: {e}")
            self.enable_mmap_overflow = False

        # Storage instances per timeframe
        self._mmap_storages: dict[str, MemoryMappedStorage] = {}
        self._overflow_stats: dict[str, dict[str, Any]] = {}

        # Track what's been overflowed
        self._overflowed_ranges: dict[str, list[tuple[datetime, datetime]]] = {}

    async def _check_overflow_needed(self, timeframe: str) -> bool:
        """
        Check if overflow to disk is needed for a timeframe.

        Args:
            timeframe: Timeframe to check

        Returns:
            True if overflow is needed
        """
        if not self.enable_mmap_overflow:
            return False

        if timeframe not in self.data:
            return False

        current_bars = len(self.data[timeframe])
        max_bars = self.max_bars_per_timeframe

        # Check if we've exceeded threshold
        return bool(current_bars > (max_bars * self.overflow_threshold))

    async def _overflow_to_disk(self, timeframe: str) -> None:
        """
        Overflow oldest data to memory-mapped storage.

        Note: Assumes the data_lock is already held by the caller.

        Args:
            timeframe: Timeframe to overflow
        """
        try:
            # NOTE: Don't acquire data_lock here - caller should hold it
            df = self.data.get(timeframe)
            if df is None or df.is_empty():
                return

            # Calculate how many bars to overflow (keep 50% in memory)
            total_bars = len(df)
            bars_to_keep = int(self.max_bars_per_timeframe * 0.5)
            bars_to_overflow = total_bars - bars_to_keep

            if bars_to_overflow <= 0:
                return

            # Split data
            overflow_df = df.head(bars_to_overflow)
            remaining_df = df.tail(bars_to_keep)

            # Get or create storage for this timeframe
            storage = self._get_or_create_storage(timeframe)

            # Generate unique key based on time range
            start_time = overflow_df["timestamp"].min()
            end_time = overflow_df["timestamp"].max()
            # Handle both datetime and other types
            if isinstance(start_time, datetime) and isinstance(end_time, datetime):
                start_str = start_time.isoformat()
                end_str = end_time.isoformat()
            else:
                start_str = str(start_time)
                end_str = str(end_time)
            key = f"{timeframe}_{start_str}_{end_str}"

            # Write to disk
            success = storage.write_dataframe(overflow_df, key=key)

            if success:
                # Update in-memory data
                self.data[timeframe] = remaining_df

                # Track overflow range
                if timeframe not in self._overflowed_ranges:
                    self._overflowed_ranges[timeframe] = []
                # Only track if times are datetime objects
                if isinstance(start_time, datetime) and isinstance(end_time, datetime):
                    self._overflowed_ranges[timeframe].append((start_time, end_time))

                # Update stats
                if timeframe not in self._overflow_stats:
                    self._overflow_stats[timeframe] = {
                        "overflow_count": 0,
                        "total_bars_overflowed": 0,
                        "last_overflow": None,
                    }

                self._overflow_stats[timeframe]["overflow_count"] += 1
                self._overflow_stats[timeframe]["total_bars_overflowed"] += (
                    bars_to_overflow
                )
                self._overflow_stats[timeframe]["last_overflow"] = datetime.now()

                logger.info(
                    f"Overflowed {bars_to_overflow} bars for {timeframe} to disk. "
                    f"Key: {key}"
                )

                # Update memory stats
                self.memory_stats["bars_overflowed"] = (
                    self.memory_stats.get("bars_overflowed", 0) + bars_to_overflow
                )

        except Exception as e:
            logger.error(f"Error overflowing {timeframe} to disk: {e}")

    def _get_or_create_storage(self, timeframe: str) -> MemoryMappedStorage:
        """
        Get or create memory-mapped storage for a timeframe.

        Args:
            timeframe: Timeframe identifier

        Returns:
            MemoryMappedStorage instance
        """
        if timeframe not in self._mmap_storages:
            filename = self.mmap_storage_path / f"{self.instrument}_{timeframe}.mmap"
            storage = MemoryMappedStorage(filename)
            storage.open()
            self._mmap_storages[timeframe] = storage

        return self._mmap_storages[timeframe]

    async def get_historical_data(
        self,
        timeframe: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> pl.DataFrame | None:
        """
        Get data including both in-memory and overflowed data.

        Args:
            timeframe: Timeframe to retrieve
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Combined DataFrame or None
        """
        try:
            all_data = []

            # Check overflowed data first
            if (
                timeframe in self._overflowed_ranges
                and timeframe in self._mmap_storages
            ):
                storage = self._mmap_storages[timeframe]

                for overflow_start, overflow_end in self._overflowed_ranges[timeframe]:
                    # Check if this range overlaps with requested range
                    if start_time and overflow_end < start_time:
                        continue
                    if end_time and overflow_start > end_time:
                        continue

                    # Load this chunk
                    key = f"{timeframe}_{overflow_start.isoformat()}_{overflow_end.isoformat()}"
                    chunk = storage.read_dataframe(key)

                    if chunk is not None:
                        # Apply time filter if needed
                        if start_time or end_time:
                            mask = pl.lit(True)
                            if start_time:
                                mask = mask & (pl.col("timestamp") >= start_time)
                            if end_time:
                                mask = mask & (pl.col("timestamp") <= end_time)
                            chunk = chunk.filter(mask)

                        if not chunk.is_empty():
                            all_data.append(chunk)

            # Add in-memory data
            if timeframe in self.data:
                memory_df = self.data[timeframe]
                if not memory_df.is_empty():
                    # Apply time filter if needed
                    if start_time or end_time:
                        mask = pl.lit(True)
                        if start_time:
                            mask = mask & (pl.col("timestamp") >= start_time)
                        if end_time:
                            mask = mask & (pl.col("timestamp") <= end_time)
                        memory_df = memory_df.filter(mask)

                    if not memory_df.is_empty():
                        all_data.append(memory_df)

            # Combine all data
            if all_data:
                combined = pl.concat(all_data)
                # Sort by timestamp and remove duplicates
                combined = combined.sort("timestamp").unique(subset=["timestamp"])
                return combined

            return None

        except Exception as e:
            logger.error(f"Error retrieving historical data: {e}")
            return None

    async def cleanup_overflow_storage(self) -> None:
        """Clean up old overflow files and close storage instances."""
        try:
            # Close all storage instances properly
            for timeframe, storage in list(self._mmap_storages.items()):
                try:
                    storage.close()
                    logger.debug(f"Closed mmap storage for {timeframe}")
                except Exception as e:
                    logger.warning(f"Error closing storage for {timeframe}: {e}")
            self._mmap_storages.clear()

            # Clean up old files based on config
            cleanup_days = getattr(self, "config", {}).get("mmap_cleanup_days", 7)
            if cleanup_days > 0:
                cutoff_time = datetime.now() - timedelta(days=cleanup_days)
                try:
                    for file_path in self.mmap_storage_path.glob("*.mmap"):
                        if file_path.stat().st_mtime < cutoff_time.timestamp():
                            file_path.unlink()
                            # Also remove metadata file
                            meta_path = file_path.with_suffix(".meta")
                            if meta_path.exists():
                                meta_path.unlink()
                            logger.info(f"Removed old overflow file: {file_path.name}")
                except Exception as e:
                    logger.warning(f"Error cleaning old files: {e}")

            logger.info("Cleaned up overflow storage")

        except Exception as e:
            logger.error(f"Error cleaning up overflow storage: {e}")

    def __del__(self) -> None:
        """Ensure cleanup on deletion."""
        # Synchronous cleanup for destructor
        if hasattr(self, "_mmap_storages"):
            for storage in self._mmap_storages.values():
                with suppress(Exception):
                    storage.close()

    async def get_overflow_stats_summary(self) -> dict[str, Any]:
        """
        Get statistics about overflow storage.

        Returns:
            Dictionary with overflow statistics
        """
        total_overflowed = sum(
            stats.get("total_bars_overflowed", 0)
            for stats in self._overflow_stats.values()
        )

        storage_sizes = {}
        for tf, storage in self._mmap_storages.items():
            info = storage.get_info()
            storage_sizes[tf] = info.get("size_mb", 0)

        return {
            "enabled": self.enable_mmap_overflow,
            "threshold": self.overflow_threshold,
            "storage_path": str(self.mmap_storage_path),
            "total_bars_overflowed": total_overflowed,
            "overflow_stats_by_timeframe": self._overflow_stats,
            "storage_sizes_mb": storage_sizes,
            "overflowed_ranges": {
                tf: [(str(start), str(end)) for start, end in ranges]
                for tf, ranges in self._overflowed_ranges.items()
            },
        }

    async def restore_from_overflow(self, timeframe: str, bars: int) -> bool:
        """
        Restore data from overflow storage back to memory.

        Args:
            timeframe: Timeframe to restore
            bars: Number of bars to restore

        Returns:
            Success status
        """
        try:
            if timeframe not in self._overflowed_ranges:
                return False

            storage = self._get_or_create_storage(timeframe)

            # Get the most recent overflow
            if self._overflowed_ranges[timeframe]:
                latest_range = self._overflowed_ranges[timeframe][-1]
                key = f"{timeframe}_{latest_range[0].isoformat()}_{latest_range[1].isoformat()}"

                # Read from storage
                overflow_df = storage.read_dataframe(key)
                if overflow_df is not None:
                    # Take the requested number of bars from the end
                    restore_df = overflow_df.tail(bars)

                    # Import here to avoid circular dependency
                    from project_x_py.utils.lock_optimization import AsyncRWLock

                    # Use appropriate lock method based on lock type
                    if isinstance(self.data_lock, AsyncRWLock):
                        async with self.data_lock.write_lock():
                            # Prepend to current data
                            if timeframe in self.data:
                                self.data[timeframe] = pl.concat(
                                    [restore_df, self.data[timeframe]]
                                )
                            else:
                                self.data[timeframe] = restore_df
                    else:
                        async with self.data_lock:
                            # Prepend to current data
                            if timeframe in self.data:
                                self.data[timeframe] = pl.concat(
                                    [restore_df, self.data[timeframe]]
                                )
                            else:
                                self.data[timeframe] = restore_df

                    logger.info(
                        f"Restored {len(restore_df)} bars for {timeframe} from overflow"
                    )
                    return True

            return False

        except Exception as e:
            logger.error(f"Error restoring from overflow: {e}")
            return False

    async def _perform_overflow(self, timeframe: str) -> None:
        """
        Perform overflow operation for a specific timeframe.

        Args:
            timeframe: Timeframe to overflow data for
        """
        try:
            # Import here to avoid circular dependency
            from project_x_py.utils.lock_optimization import AsyncRWLock

            # Use appropriate lock method based on lock type
            if hasattr(self, "data_rw_lock") and isinstance(
                getattr(self, "data_rw_lock", None), AsyncRWLock
            ):
                async with self.data_rw_lock.write_lock():
                    await self._overflow_to_disk(timeframe)
            elif hasattr(self, "data_lock"):
                async with self.data_lock:
                    await self._overflow_to_disk(timeframe)
            else:
                # No lock available, proceed anyway
                await self._overflow_to_disk(timeframe)

        except Exception as e:
            logger.error(f"Error performing overflow for {timeframe}: {e}")

    async def _retrieve_overflow_data(
        self, timeframe: str, start_time: datetime, end_time: datetime
    ) -> pl.DataFrame | None:
        """
        Retrieve overflowed data for a specific time range.

        Args:
            timeframe: Timeframe to retrieve data for
            start_time: Start of time range
            end_time: End of time range

        Returns:
            DataFrame with overflowed data or None
        """
        if timeframe not in self._mmap_storages:
            return None

        try:
            storage = self._mmap_storages[timeframe]

            # Find matching overflow ranges
            matching_data = []
            for overflow_start, overflow_end in self._overflowed_ranges.get(
                timeframe, []
            ):
                # Check if this range overlaps with requested range
                if overflow_end >= start_time and overflow_start <= end_time:
                    key = f"{timeframe}_{overflow_start.isoformat()}_{overflow_end.isoformat()}"
                    chunk = storage.read_dataframe(key)
                    if chunk is not None:
                        # Filter to exact time range
                        mask = (pl.col("timestamp") >= start_time) & (
                            pl.col("timestamp") <= end_time
                        )
                        filtered_chunk = chunk.filter(mask)
                        if not filtered_chunk.is_empty():
                            matching_data.append(filtered_chunk)

            if matching_data:
                return pl.concat(matching_data).sort("timestamp")

            return None

        except Exception as e:
            logger.error(f"Error retrieving overflow data: {e}")
            return None

    async def get_combined_data(
        self, timeframe: str, start_time: datetime, end_time: datetime
    ) -> pl.DataFrame | None:
        """
        Get combined data from both memory and overflow storage.

        Args:
            timeframe: Timeframe to retrieve
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Combined DataFrame or None
        """
        # Get memory data
        memory_data = None
        if timeframe in self.data:
            df = self.data[timeframe]
            if not df.is_empty():
                mask = (pl.col("timestamp") >= start_time) & (
                    pl.col("timestamp") <= end_time
                )
                memory_data = df.filter(mask)

        # Get overflow data
        overflow_data = await self._retrieve_overflow_data(
            timeframe, start_time, end_time
        )

        # Combine data
        if memory_data is not None and overflow_data is not None:
            combined = pl.concat([overflow_data, memory_data]).sort("timestamp")
            return combined.unique("timestamp", keep="last")
        elif memory_data is not None:
            return memory_data
        elif overflow_data is not None:
            return overflow_data
        else:
            return None

    async def _cleanup_old_overflow_files(self, max_age_days: int = 7) -> None:
        """
        Clean up old overflow files based on age.

        Args:
            max_age_days: Maximum age in days for files to keep
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=max_age_days)

            for file_path in self.mmap_storage_path.glob("*.mmap"):
                if file_path.stat().st_mtime < cutoff_time.timestamp():
                    file_path.unlink()
                    # Also remove metadata file
                    meta_path = file_path.with_suffix(".meta")
                    if meta_path.exists():
                        meta_path.unlink()
                    logger.info(f"Cleaned up old overflow file: {file_path.name}")

        except Exception as e:
            logger.error(f"Error cleaning up old overflow files: {e}")

    async def get_total_data_count(self, timeframe: str) -> int:
        """
        Get total count of bars including both memory and overflow storage.

        Args:
            timeframe: Timeframe to count

        Returns:
            Total number of bars
        """
        total_count = 0

        # Count in-memory bars
        if timeframe in self.data:
            total_count += len(self.data[timeframe])

        # Count overflowed bars
        if timeframe in self._overflow_stats:
            total_count += self._overflow_stats[timeframe].get(
                "total_bars_overflowed", 0
            )

        return total_count

    async def get_overflow_stats(self, timeframe: str) -> dict[str, Any]:
        """
        Get overflow statistics for a specific timeframe.

        Args:
            timeframe: Timeframe to get stats for

        Returns:
            Dictionary with overflow statistics
        """
        if timeframe not in self._overflow_stats:
            return {
                "total_overflowed_bars": 0,
                "disk_storage_size_mb": 0.0,
                "overflow_operations_count": 0,
            }

        stats = self._overflow_stats[timeframe].copy()

        # Get disk storage size
        disk_size_mb = 0.0
        if timeframe in self._mmap_storages:
            storage = self._mmap_storages[timeframe]
            info = storage.get_info()
            disk_size_mb = info.get("size_mb", 0.0)

        return {
            "total_overflowed_bars": stats.get("total_bars_overflowed", 0),
            "disk_storage_size_mb": disk_size_mb,
            "overflow_operations_count": stats.get("overflow_count", 0),
        }
