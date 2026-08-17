"""Unit tests for shared risk helpers."""

from risk import capped_weight, position_size_by_risk, split_take_profit_quantities


def test_position_size_by_risk_scales_with_stop_distance():
    assert position_size_by_risk(100_000, 0.01, 100, 99) == 1000


def test_capped_weight_limits_allocation():
    assert capped_weight(0.5, 0.3) == 0.3


def test_split_take_profit_quantities():
    assert split_take_profit_quantities(10) == (5, 5)
    assert split_take_profit_quantities(1) == (1, 0)
