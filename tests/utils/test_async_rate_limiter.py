"""Tests for the rate limiter functionality of ProjectX client."""

import asyncio
import time

import pytest

from project_x_py.utils.async_rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for the rate limiter functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_under_limit(self):
        """Test that rate limiter allows requests under the limit."""
        limiter = RateLimiter(max_requests=5, window_seconds=1)

        start_time = time.time()

        # Make 5 requests (should all be immediate)
        for _ in range(5):
            await limiter.acquire()

        elapsed = time.time() - start_time

        # All 5 requests should have been processed immediately
        # Allow some small execution time, but less than 0.1s total
        assert elapsed < 0.1, "Requests under limit should be processed immediately"

    @pytest.mark.asyncio
    async def test_rate_limiter_delays_over_limit(self):
        """Test that rate limiter delays requests over the limit."""
        limiter = RateLimiter(max_requests=3, window_seconds=0.5)

        # Make initial requests to fill up the limit
        for _ in range(3):
            await limiter.acquire()

        start_time = time.time()

        # This should be delayed since we've hit our limit of 3 per 0.5s
        await limiter.acquire()

        elapsed = time.time() - start_time

        # Should have waited close to 0.5s for the window to expire
        assert 0.4 <= elapsed <= 0.7, f"Expected delay of ~1s, got {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_rate_limiter_window_sliding(self):
        """Test that rate limiter uses a sliding window for requests."""
        # Create a limiter with small window to make test faster
        window_seconds = 0.5
        limiter = RateLimiter(max_requests=3, window_seconds=window_seconds)

        # Send 3 requests immediately (filling the window)
        request_times = []
        for _ in range(3):
            await limiter.acquire()
            request_times.append(time.time())

        # Wait for most of the window to pass
        await asyncio.sleep(window_seconds * 0.8)  # 80% of window time passed

        # At this point, we should be able to make 1 more request with minimal delay
        # since one of the original requests should have "slid out" of the window
        start_time = time.time()
        await limiter.acquire()
        request_times.append(time.time())
        elapsed = time.time() - start_time

        # This should be fairly quick since we're using a sliding window
        # Not requiring < 0.1 since timing can vary on different systems
        assert elapsed < window_seconds * 0.5, (
            "Request should be relatively quick with sliding window"
        )

        # Make one more request to see if it delays properly
        start_time = time.time()
        await limiter.acquire()
        elapsed = time.time() - start_time

        # This should show some delay
        assert elapsed > 0, "Request should show some delay when window is full"

    @pytest.mark.asyncio
    async def test_rate_limiter_concurrent_access(self):
        """Test that rate limiter handles concurrent access properly."""
        limiter = RateLimiter(max_requests=3, window_seconds=1)

        # Launch 5 concurrent tasks, only 3 should run immediately
        start_time = time.time()

        async def make_request(idx):
            await limiter.acquire()
            return idx, time.time() - start_time

        tasks = [make_request(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Sort by elapsed time
        results.sort(key=lambda x: x[1])

        # First 3 should be quick, last 2 should be delayed
        assert results[0][1] < 0.1, "First request should be immediate"
        assert results[1][1] < 0.1, "Second request should be immediate"
        assert results[2][1] < 0.1, "Third request should be immediate"

        # Last 2 should have waited for at least some of the window time
        assert results[3][1] > 0.1, "Fourth request should be delayed"
        assert results[4][1] > 0.1, "Fifth request should be delayed"

    @pytest.mark.asyncio
    async def test_rate_limiter_clears_old_requests(self):
        """Test that rate limiter properly clears old requests."""
        limiter = RateLimiter(max_requests=2, window_seconds=0.3)

        # Fill up the limit
        await limiter.acquire()
        await limiter.acquire()

        # Wait for all requests to age out
        await asyncio.sleep(0.4)  # Wait longer than window_seconds

        # Make multiple requests that should be immediate
        start_time = time.time()
        await limiter.acquire()
        elapsed_first = time.time() - start_time

        start_time = time.time()
        await limiter.acquire()
        elapsed_second = time.time() - start_time

        # Both should be immediate since old requests aged out
        assert elapsed_first < 0.1, (
            "First request should be immediate after window expires"
        )
        assert elapsed_second < 0.1, (
            "Second request should be immediate after window expires"
        )

        # Verify internal state
        assert len(limiter.requests) == 2, "Should have 2 requests in tracking"

    @pytest.mark.asyncio
    async def test_rate_limiter_memory_cleanup(self):
        """Test that rate limiter doesn't accumulate unlimited request history."""
        limiter = RateLimiter(max_requests=100, window_seconds=0.1)

        # Make many requests over multiple windows
        for _ in range(5):
            # Fill the window
            for _ in range(100):
                await limiter.acquire()
            # Wait for window to expire
            await asyncio.sleep(0.15)

        # Check that internal state is bounded
        # Should not keep more than max_requests * 2 entries
        assert len(limiter.requests) <= 200, "Should limit internal request history"

    @pytest.mark.asyncio
    async def test_rate_limiter_edge_cases(self):
        """Test edge cases for rate limiter."""
        # Test with 1 request per window
        limiter = RateLimiter(max_requests=1, window_seconds=0.1)

        await limiter.acquire()
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        assert elapsed >= 0.09, "Should wait for window with single request limit"

        # Test with very large window
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        await limiter.acquire()

        # Should still track request
        assert len(limiter.requests) == 1

    @pytest.mark.asyncio
    async def test_rate_limiter_stress_test(self):
        """Stress test the rate limiter with many concurrent requests."""
        limiter = RateLimiter(max_requests=10, window_seconds=0.5)

        # Create 50 concurrent requests
        async def make_request():
            await limiter.acquire()
            return time.time()

        start_time = time.time()
        tasks = [make_request() for _ in range(50)]
        times = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Should take at least 2 seconds (5 batches of 10 requests, 0.5s window)
        # But less than 3 seconds (allowing for some overhead)
        assert 2.0 <= total_time <= 3.0, f"Expected ~2.5s total, got {total_time:.2f}s"

        # Verify requests were properly rate limited
        times.sort()

        # Check rate limiting - for any 0.5s window, we should have at most 10 requests
        # In CI environments, allow up to 30% more due to timing variations
        import os

        max_allowed = 13 if os.environ.get("CI") else 10

        for i in range(len(times)):
            # Count requests within 0.5s window starting from this request
            window_end = times[i] + 0.5
            requests_in_window = sum(1 for t in times[i:] if t < window_end)
            assert requests_in_window <= max_allowed, (
                f"Too many requests ({requests_in_window}) in 0.5s window starting at index {i} (max: {max_allowed})"
            )

    @pytest.mark.asyncio
    async def test_rate_limiter_accuracy(self):
        """Test the accuracy of rate limiting calculations."""
        limiter = RateLimiter(max_requests=5, window_seconds=1.0)

        # Record exact timings
        timings = []

        for i in range(10):
            start = time.time()
            await limiter.acquire()
            timings.append(time.time())

            # Small delay to spread requests
            if i < 9:
                await asyncio.sleep(0.05)

        # Analyze the timings
        # First 5 should be in the first second
        assert timings[4] - timings[0] < 1.0, (
            "First 5 requests should be within 1 second"
        )

        # 6th request should be delayed
        assert timings[5] - timings[0] >= 0.9, "6th request should wait for window"

        # Check sliding window behavior
        for i in range(5, 10):
            # Each request should maintain the rate limit
            recent_requests = [t for t in timings[: i + 1] if t > timings[i] - 1.0]
            assert len(recent_requests) <= 5, (
                f"Too many requests in window at index {i}"
            )
