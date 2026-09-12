import pytest
from app.utils.dummy_data import generate_stock_data
from app.engine.broker import SimulatedBroker
from app.engine.backtester import BacktestRunner
from app.engine.macd import MACDStrategy
from app.engine.rsi import RSIStrategy
from app.engine.sma_crossover import SMACrossoverStrategy
from app.engine.bollinger import BollingerBandsStrategy

STRATEGIES = [MACDStrategy, RSIStrategy, SMACrossoverStrategy, BollingerBandsStrategy]


@pytest.mark.parametrize("StrategyClass", STRATEGIES)
def test_strategy_runs_end_to_end_and_returns_complete_results(StrategyClass):
    df = generate_stock_data("SBIN", days=300, seed=42)
    broker = SimulatedBroker(100000)
    strategy = StrategyClass(broker)
    runner = BacktestRunner(broker, strategy)
    runner.load_data(df)
    results = runner.run()

    expected_keys = {
        "initial_capital", "final_capital", "total_taxes", "realized_pnl",
        "roi", "max_drawdown", "win_rate", "total_trades", "trades", "equity_curve",
    }
    assert expected_keys.issubset(results.keys())
    assert results["initial_capital"] == 100000
    assert len(results["equity_curve"]) == len(df)
    assert results["final_capital"] >= 0


@pytest.mark.parametrize("StrategyClass", STRATEGIES)
def test_strategy_never_oversells_a_position(StrategyClass):
    df = generate_stock_data("RELIANCE", days=300, seed=7)
    broker = SimulatedBroker(50000)
    strategy = StrategyClass(broker)
    runner = BacktestRunner(broker, strategy)
    runner.load_data(df)
    runner.run()

    for trade in broker.history:
        assert trade["qty"] > 0
        assert trade["price"] > 0
