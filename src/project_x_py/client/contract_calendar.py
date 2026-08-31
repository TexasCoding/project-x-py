"""CME futures month codes and prior-contract-id iteration.

Used by historical bar stitching. No I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

CME_MONTH_CODES = "FGHJKMNQUVXZ"

_CONTRACT_ID_RE = re.compile(r"^CON\.[A-Z]\.[A-Z]{2}\.(.+)\.([FGHJKMNQUVXZ])(\d{1,2})$")


def parse_contract_id(contract_id: str) -> tuple[str, str, int] | None:
    """Return (root, month_code, two_digit_year) or None if not a CON. id."""
    match = _CONTRACT_ID_RE.match(contract_id)
    if match is None:
        return None
    root, month_code, year_s = match.groups()
    return root, month_code, int(year_s)


def iter_prior_contract_ids(contract_id: str, max_count: int = 24) -> Iterator[str]:
    """Yield previous CME month ids, wrapping F → previous-year Z.

    Bounded by ``max_count`` so callers can ``list()`` safely.
    """
    parsed = parse_contract_id(contract_id)
    if parsed is None or max_count <= 0:
        return
    _root, month_code, year = parsed
    prefix = contract_id.rsplit(".", 1)[0]
    idx = CME_MONTH_CODES.index(month_code)
    yielded = 0
    while yielded < max_count:
        idx -= 1
        if idx < 0:
            idx = len(CME_MONTH_CODES) - 1
            year -= 1
            if year < 0:
                return
        yield f"{prefix}.{CME_MONTH_CODES[idx]}{year:02d}"
        yielded += 1
