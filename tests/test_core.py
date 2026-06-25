"""Real (small) tests on the valuation and risk math. Run: pytest -q"""
import pytest

from data_pipeline.sample_data import generate
from finance import valuation, factors
from risk.montecarlo_var import monte_carlo_var


@pytest.fixture(scope="module", autouse=True)
def seeded_db():
    generate(seed=42)
    yield


def test_dcf_basic_consistency():
    r = valuation.dcf("NVDA", wacc=0.10, term_growth=0.03)
    assert r.fair_value_per_share > 0
    assert r.current_price > 0
    # upside is internally consistent with fair value / price
    expected = (r.fair_value_per_share / r.current_price - 1) * 100
    assert abs(expected - r.upside_pct) < 0.5


def test_dcf_higher_wacc_lowers_value():
    low = valuation.dcf("NVDA", wacc=0.09, term_growth=0.03).fair_value_per_share
    high = valuation.dcf("NVDA", wacc=0.12, term_growth=0.03).fair_value_per_share
    assert high < low  # discounting harder reduces value


def test_sensitivity_grid_shape():
    r = valuation.dcf("NVDA")
    assert len(r.sensitivity) == 5
    assert all("wacc" in row for row in r.sensitivity)


def test_factor_table_has_universe():
    rows = factors.factor_table()
    tickers = {r["ticker"] for r in rows}
    assert {"NVDA", "AMD", "TSM"}.issubset(tickers)


def test_var_is_positive_and_ordered():
    out = monte_carlo_var(["NVDA", "AMD"], n_paths=50_000, seed=1)
    assert out["VaR_pct"] > 0
    # CVaR (expected shortfall) is at least as large as VaR
    assert out["CVaR_pct"] >= out["VaR_pct"]


def test_var_more_names_lowers_risk():
    one = monte_carlo_var(["NVDA"], n_paths=50_000, seed=1)["VaR_pct"]
    many = monte_carlo_var(["NVDA", "AMD", "TSM", "MSFT"], n_paths=50_000, seed=1)["VaR_pct"]
    assert many < one  # diversification reduces portfolio VaR
