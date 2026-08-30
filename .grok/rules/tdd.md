# TDD (SDK overlay)

Superpowers `test-driven-development` owns the RED-GREEN-REFACTOR ritual.
This file only adds project-x-py constraints.

- Tests are the specification. If code fails a test, fix the code.
- Tests live in `tests/test_*.py` (or `tests/unit/`, `tests/integration/`).
- Async tests use `@pytest.mark.asyncio`. Do not use `asyncio.run()` in tests.
- Bug fixes start with a failing reproduction test.
- Examples are not the test suite. Run examples with `./test.sh`; run tests with `uv run pytest`.
