"""Unit tests for CME contract-id calendar helpers."""

from project_x_py.client.contract_calendar import (
    CME_MONTH_CODES,
    iter_prior_contract_ids,
    parse_contract_id,
)


def test_cme_month_codes_are_calendar_order():
    assert CME_MONTH_CODES == "FGHJKMNQUVXZ"


def test_parse_contract_id_mnq_u26():
    assert parse_contract_id("CON.F.US.MNQ.U26") == ("MNQ", "U", 26)


def test_parse_contract_id_digit_root():
    assert parse_contract_id("CON.F.US.M6E.U26") == ("M6E", "U", 26)


def test_parse_contract_id_rejects_garbage():
    assert parse_contract_id("MNQ") is None
    assert parse_contract_id("CON.F.US.MNQ") is None
    assert parse_contract_id("") is None


def test_iter_prior_from_u26_starts_q_n_m():
    prior = list(iter_prior_contract_ids("CON.F.US.MNQ.U26", max_count=3))
    assert prior == [
        "CON.F.US.MNQ.Q26",
        "CON.F.US.MNQ.N26",
        "CON.F.US.MNQ.M26",
    ]


def test_iter_prior_wraps_year_at_january():
    prior = list(iter_prior_contract_ids("CON.F.US.MNQ.F26", max_count=1))
    assert prior == ["CON.F.US.MNQ.Z25"]


def test_iter_prior_empty_for_invalid_id():
    assert list(iter_prior_contract_ids("MNQ")) == []
