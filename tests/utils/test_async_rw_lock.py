"""Tests for AsyncRWLock coordination, timeouts, and cancellation (#137)."""

from __future__ import annotations

import asyncio

import pytest

from project_x_py.utils.lock_optimization import AsyncRWLock


@pytest.mark.asyncio
@pytest.mark.unit
async def test_concurrent_readers_are_allowed() -> None:
    lock = AsyncRWLock("readers")
    in_cs = 0
    max_in_cs = 0
    started = asyncio.Event()

    async def reader() -> None:
        nonlocal in_cs, max_in_cs
        async with lock.read_lock():
            in_cs += 1
            max_in_cs = max(max_in_cs, in_cs)
            started.set()
            await asyncio.sleep(0.05)
            in_cs -= 1

    await asyncio.gather(reader(), reader(), reader())
    assert max_in_cs == 3
    assert lock.reader_count == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_readers_wait_for_active_writer() -> None:
    lock = AsyncRWLock("writer-blocks-readers")
    writer_holds = asyncio.Event()
    reader_entered = asyncio.Event()

    async def writer() -> None:
        async with lock.write_lock():
            writer_holds.set()
            await asyncio.sleep(0.15)

    async def reader() -> None:
        await writer_holds.wait()
        async with lock.read_lock():
            reader_entered.set()

    wtask = asyncio.create_task(writer())
    rtask = asyncio.create_task(reader())
    await writer_holds.wait()
    await asyncio.sleep(0.03)
    assert not reader_entered.is_set()
    await asyncio.gather(wtask, rtask)
    assert reader_entered.is_set()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_writer_waits_for_active_readers() -> None:
    lock = AsyncRWLock("readers-block-writer")
    reader_holds = asyncio.Event()
    writer_entered = asyncio.Event()

    async def reader() -> None:
        async with lock.read_lock():
            reader_holds.set()
            await asyncio.sleep(0.15)

    async def writer() -> None:
        await reader_holds.wait()
        async with lock.write_lock():
            writer_entered.set()

    rtask = asyncio.create_task(reader())
    wtask = asyncio.create_task(writer())
    await reader_holds.wait()
    await asyncio.sleep(0.03)
    assert not writer_entered.is_set()
    await asyncio.gather(rtask, wtask)
    assert writer_entered.is_set()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_waiting_writer_blocks_new_readers() -> None:
    lock = AsyncRWLock("writer-preference")
    reader1_holds = asyncio.Event()
    writer_waiting = asyncio.Event()
    writer_entered = asyncio.Event()
    reader2_entered = asyncio.Event()

    async def reader1() -> None:
        async with lock.read_lock():
            reader1_holds.set()
            await asyncio.sleep(0.2)

    async def writer() -> None:
        await reader1_holds.wait()
        writer_waiting.set()
        async with lock.write_lock():
            writer_entered.set()

    async def reader2() -> None:
        await writer_waiting.wait()
        await asyncio.sleep(0.02)
        async with lock.read_lock():
            reader2_entered.set()

    tasks = [
        asyncio.create_task(reader1()),
        asyncio.create_task(writer()),
        asyncio.create_task(reader2()),
    ]
    await reader1_holds.wait()
    await writer_waiting.wait()
    await asyncio.sleep(0.05)
    assert not reader2_entered.is_set()
    await asyncio.gather(*tasks)
    assert writer_entered.is_set()
    assert reader2_entered.is_set()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_read_lock_timeout_raises() -> None:
    lock = AsyncRWLock("read-timeout")

    async def writer() -> None:
        async with lock.write_lock():
            await asyncio.sleep(1.0)

    wtask = asyncio.create_task(writer())
    await asyncio.sleep(0.02)
    with pytest.raises(TimeoutError):
        async with lock.read_lock(timeout=0.05):
            raise AssertionError("reader must not enter while writer holds the lock")
    wtask.cancel()
    await asyncio.gather(wtask, return_exceptions=True)
    stats = await lock.get_stats()
    assert stats.timeouts >= 1
    assert lock.reader_count == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_write_lock_timeout_raises() -> None:
    lock = AsyncRWLock("write-timeout")

    async def reader() -> None:
        async with lock.read_lock():
            await asyncio.sleep(1.0)

    rtask = asyncio.create_task(reader())
    await asyncio.sleep(0.02)
    with pytest.raises(TimeoutError):
        async with lock.write_lock(timeout=0.05):
            raise AssertionError("writer must not enter while a reader holds the lock")
    rtask.cancel()
    await asyncio.gather(rtask, return_exceptions=True)
    assert lock.reader_count == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_write_lock_is_reentrant() -> None:
    lock = AsyncRWLock("reentrant-write")
    nested = False
    async with lock.write_lock():
        async with lock.write_lock():
            nested = True
    assert nested is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cancelled_reader_releases_count() -> None:
    lock = AsyncRWLock("cancel-reader")
    entered = asyncio.Event()

    async def reader() -> None:
        async with lock.read_lock():
            entered.set()
            await asyncio.sleep(10)

    task = asyncio.create_task(reader())
    await entered.wait()
    assert lock.reader_count == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert lock.reader_count == 0

    async with lock.write_lock(timeout=0.2):
        pass
