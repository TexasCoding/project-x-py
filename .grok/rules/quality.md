# Code quality

- Python 3.12+ type hints: `X | Y`, `dict[str, Any]`, `list[int]`. No `Optional`/`Union`/`Dict`.
- `isinstance(value, int | float)` not `(int, float)`.
- Polars only for DataFrames. Never import pandas.
- Prices: `Decimal`. Align to instrument tick size before sending orders.
- Wrap `httpx` / gateway errors in `project_x_py.exceptions`. No bare `except:`.
- Validate external payloads before trading actions.
- Bounded in-memory collections (bars, trades, depth). No unbounded growth.
- Prefer vectorized Polars over Python loops on market data.
