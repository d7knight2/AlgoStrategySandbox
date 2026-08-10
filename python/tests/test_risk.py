"""Risk engine tests."""

from src.risk import RiskEngine, RiskLimits, ProposedTrade, RiskDecision


def test_allow_small_trade():
    engine = RiskEngine(RiskLimits(max_order_dollars=250))
    trade = ProposedTrade(symbol="SPY", side="buy", notional=100.0)
    result = engine.evaluate(
        trade,
        portfolio_value=10000.0,
        current_positions=[],
        buying_power=5000.0,
    )
    assert result.decision == RiskDecision.ALLOW
    assert result.reasons == []


def test_reject_oversized_order():
    engine = RiskEngine(RiskLimits(max_order_dollars=250))
    trade = ProposedTrade(symbol="SPY", side="buy", notional=500.0)
    result = engine.evaluate(
        trade,
        portfolio_value=10000.0,
        current_positions=[],
        buying_power=5000.0,
    )
    assert result.decision == RiskDecision.REJECT
    assert any("max_order_dollars" in r for r in result.reasons)


def test_kill_switch():
    engine = RiskEngine()
    engine.pause_trading()
    trade = ProposedTrade(symbol="SPY", side="buy", notional=50.0)
    result = engine.evaluate(
        trade,
        portfolio_value=10000.0,
        current_positions=[],
        buying_power=5000.0,
    )
    assert result.decision == RiskDecision.REJECT
    assert any("pause" in r.lower() for r in result.reasons)
