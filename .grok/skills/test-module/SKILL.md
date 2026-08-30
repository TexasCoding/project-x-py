---
name: test-module
description: Use when asked to write or expand a test suite for a src/project_x_py module. Triggers include /test-module, "cover this module", and "tests for order_manager".
---

# Test a module

Write pytest-asyncio tests that specify how `src/project_x_py/<module>/` should behave.

1. Read the module and its existing `tests/test_*.py` files.
2. Audit existing tests: they must assert correct behavior, not encode bugs.
3. For each gap, RED then GREEN:
   - Failing test first (`uv run pytest path::test_name` must fail)
   - Minimal implementation fix if the code is wrong
4. Cover success and error paths. One behavior per test name.
5. Markers: `unit` by default; `integration` / `realtime` / `slow` only when needed.

Do not mock away the logic under test. Do not weaken assertions to match faulty code.
