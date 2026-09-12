import pandas as pd
import pytest
from app.engine.position_sizing import (
    FullCapitalSizer, FixedFractionSizer, VolatilityTargetSizer, build_sizer,
)


def _price_df(prices):
    return pd.DataFrame({"Value": prices})


def test_full_capital_sizer_bets_everything():
    sizer = FullCapitalSizer()
    assert sizer.size(capital=10000, price=100, df=_price_df([100]), i=0) == 100


def test_full_capital_sizer_zero_on_invalid_price():
    sizer = FullCapitalSizer()
    assert sizer.size(capital=10000, price=0, df=_price_df([100]), i=0) == 0


def test_fixed_fraction_sizer_bets_only_the_configured_fraction():
    sizer = FixedFractionSizer(fraction=0.2)
    # 20% of 10000 = 2000, at price 100 -> 20 shares
    assert sizer.size(capital=10000, price=100, df=_price_df([100]), i=0) == 20


def test_fixed_fraction_sizer_clamps_fraction_to_valid_range():
    over = FixedFractionSizer(fraction=1.5)
    under = FixedFractionSizer(fraction=-0.5)
    assert over.fraction == 1.0
    assert under.fraction == 0.0


def test_volatility_target_sizer_falls_back_to_full_capital_with_insufficient_history():
    sizer = VolatilityTargetSizer(risk_per_trade=0.01)
    df = _price_df([100])
    assert sizer.size(capital=10000, price=100, df=df, i=0) == 100  # only 1 bar, can't compute stdev


def test_volatility_target_sizer_gives_smaller_position_for_choppier_stock():
    calm = _price_df([100, 100.5, 99.8, 100.3, 99.9, 100.4, 100.1, 99.7, 100.2, 100.0])
    choppy = _price_df([100, 110, 90, 115, 85, 120, 80, 125, 75, 100])

    sizer = VolatilityTargetSizer(risk_per_trade=0.01, lookback=10)
    calm_qty = sizer.size(capital=100000, price=100, df=calm, i=9)
    choppy_qty = sizer.size(capital=100000, price=100, df=choppy, i=9)

    assert calm_qty > choppy_qty


def test_volatility_target_sizer_never_exceeds_available_capital():
    # Near-zero volatility could otherwise imply a huge, unaffordable position.
    flat = _price_df([100.0] * 10)
    sizer = VolatilityTargetSizer(risk_per_trade=0.5, lookback=10)
    qty = sizer.size(capital=10000, price=100, df=flat, i=9)
    assert qty * 100 <= 10000


def test_build_sizer_defaults_to_full_capital():
    sizer = build_sizer(None)
    assert isinstance(sizer, FullCapitalSizer)


def test_build_sizer_builds_fixed_fraction_with_params():
    sizer = build_sizer({"mode": "fixed_fraction", "fraction": 0.3})
    assert isinstance(sizer, FixedFractionSizer)
    assert sizer.fraction == 0.3


def test_build_sizer_builds_volatility_target_with_params():
    sizer = build_sizer({"mode": "volatility_target", "risk_per_trade": 0.02, "lookback": 20})
    assert isinstance(sizer, VolatilityTargetSizer)
    assert sizer.risk_per_trade == 0.02
    assert sizer.lookback == 20


def test_build_sizer_rejects_unknown_mode():
    with pytest.raises(ValueError):
        build_sizer({"mode": "not_a_real_mode"})
