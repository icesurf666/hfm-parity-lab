"""Regression test: the live ``run_frac`` must keep the historical definition."""
from __future__ import annotations

import pytest
from backtest_features import run_frac as reference
from events import EVENTS
from live_features import run_frac as defective
from live_features_fixed import run_frac as fixed


@pytest.mark.parametrize("trades", EVENTS.values(), ids=EVENTS.keys())
def test_fixed_live_run_frac_matches_backtest(trades) -> None:  # type: ignore[no-untyped-def]
    assert fixed(trades) == reference(trades)


def test_original_defect_is_detectable() -> None:
    assert any(defective(trades) != reference(trades) for trades in EVENTS.values())
