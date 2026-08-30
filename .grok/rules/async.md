# Async testing

This SDK is async-only. Tests must be too.

```python
@pytest.mark.asyncio
async def test_place_order_returns_id():
    result = await manager.place_order(...)
    assert result.success is True
```

- Use `AsyncMock` for async collaborators; `aioresponses` for HTTP.
- Test async context managers with `async with` and assert cleanup after exit.
- Do not block the loop with `.result()`, `time.sleep()`, or sync I/O in async tests.
- Mark slow / live / websocket tests: `slow`, `realtime`, `integration`.
