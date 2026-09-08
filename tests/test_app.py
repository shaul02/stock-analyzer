"""בדיקות יחידה ללוגיקה הטהורה של האפליקציה (ללא רשת).

הרצה:  python -m pytest -q
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa: E402


def _synth(n: int, seed: int = 42, drift: float = 0.15) -> pd.DataFrame:
    idx = pd.bdate_range("2021-01-01", periods=n)
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(drift, 1.4, n))
    return pd.DataFrame(
        {
            "Open": close + rng.normal(0, 0.5, n),
            "High": close + np.abs(rng.normal(1, 0.6, n)),
            "Low": close - np.abs(rng.normal(1, 0.6, n)),
            "Close": close,
            "Volume": rng.integers(1_000_000, 5_000_000, n),
        },
        index=idx,
    )


@pytest.fixture(scope="module")
def df_long() -> pd.DataFrame:
    return app.add_indicators(_synth(520))


@pytest.fixture(scope="module")
def df_short() -> pd.DataFrame:
    return app.add_indicators(_synth(120, seed=7, drift=-0.2))


def test_add_indicators_columns(df_long):
    for col in ("SMA50", "SMA100", "SMA200", "RSI", "MACD", "MACD_signal", "MACD_hist",
               "BB_high", "BB_mid", "BB_low", "ATR", "ATR_pct", "ADX",
               "STOCH_K", "STOCH_D", "OBV"):
        assert col in df_long.columns, col
    assert df_long["SMA200"].notna().sum() > 200
    assert 0 <= df_long["RSI"].iloc[-1] <= 100


def test_technical_summary(df_long):
    verdict, icon, kind, score, rows = app.technical_summary(df_long)
    assert kind in {"success", "error", "info"}
    assert len(rows) >= 7
    assert verdict in {"v_bullish", "v_bearish", "v_neutral"}
    # every verdict key resolves in all 3 languages
    for lg in ("he", "en", "ru"):
        assert app.STRINGS[verdict][lg]


@pytest.mark.parametrize("info,pe", [
    ({"fiftyTwoWeekHigh": 200, "fiftyTwoWeekLow": 80, "pegRatio": 1.4}, 22.0),
    ({}, None),
])
def test_buy_recommendation(df_long, info, pe):
    r = app.buy_recommendation(df_long, info, pe)
    assert r["kind"] in {"success", "error", "info"}
    assert r["answer_key"] in {"reco_yes", "reco_no", "reco_unclear"}
    assert set(r["horizons"]) == {"short", "medium", "long"}
    for h in r["horizons"].values():
        assert isinstance(h["score"], int)
        assert h["status"] in {"pos", "neg", "neu"}


def test_i18n_all_keys_have_three_langs():
    for key, d in app.STRINGS.items():
        assert set(d) >= {"he", "en", "ru"}, key
        for lg in ("he", "en", "ru"):
            assert isinstance(d[lg], str), (key, lg)


def test_deep_translations_wellformed():
    import translations
    for src, d in translations.DEEP.items():
        assert set(d) >= {"en", "ru"}, src
        for lg in ("en", "ru"):
            assert isinstance(d[lg], str) and d[lg], (src, lg)
            # placeholders must match between source and translation
            src_ph = sorted(p for p in ("{x}", "{a}") if p in src)
            assert sorted(p for p in ("{x}", "{a}") if p in d[lg]) == src_ph, src


def test_L_helper(monkeypatch):
    monkeypatch.setattr(app, "get_lang", lambda: "he")
    assert app.L("הכנסות") == "הכנסות"
    assert app.L("עלייה של {x}% בחודש האחרון", x="5.0") == "עלייה של 5.0% בחודש האחרון"
    monkeypatch.setattr(app, "get_lang", lambda: "en")
    assert app.L("הכנסות") == "Revenue"
    assert app.L("עלייה של {x}% בחודש האחרון", x="5.0") == "Up 5.0% over the past month"
    monkeypatch.setattr(app, "get_lang", lambda: "ru")
    assert app.L("הכנסות") == "Выручка"
    assert app.L("מפתח שלא קיים בכלל") == "מפתח שלא קיים בכלל"  # missing -> source


def test_support_resistance_and_trendlines(df_long):
    lv = app.support_resistance(df_long)
    assert isinstance(lv, list) and all(isinstance(x, float) for x in lv)
    tl = app.trendlines(df_long)
    assert set(tl) <= {"support", "resistance"}
    for seg in tl.values():
        assert len(seg["x"]) == 2 and len(seg["y"]) == 2


def test_buy_recommendation_short_series_no_crash(df_short):
    r = app.buy_recommendation(df_short, {}, None)
    assert r["kind"] in {"success", "error", "info"}


def test_backtest(df_long, df_short):
    bt = app.backtest_signal(df_long)
    assert bt is not None
    assert isinstance(bt["strategy_return"], float)
    assert isinstance(bt["buyhold_return"], float)
    assert bt["hit_rate"] is None or 0.0 <= bt["hit_rate"] <= 1.0
    assert 0.0 <= bt["exposure"] <= 1.0
    assert app.backtest_signal(df_short) is None


def test_formatters():
    assert app.human_number(1_500_000_000) == "1.50B"
    assert app.human_number(None) == "—"
    assert app.fmt(0.0345, pct=True) == "3.45%"
    assert app.fmt(None) == "—"
    assert app.fmt(float("nan")) == "—"
    assert app.ccy_sym("USD") == "$"
    assert app.ccy_sym("ILS") == "₪"
    assert app.price_str(1234.5, "EUR") == "€1,234.50"
    assert app.price_str(None) == "—"


def test_pe_ratio():
    assert app.pe_ratio({}, None) == (None, "לא זמין")
    val, src = app.pe_ratio({"trailingEps": 5}, 100)
    assert round(val, 2) == 20.0 and "EPS" in src


def test_financial_sections_sparse():
    sec = app.financial_sections(
        {"marketCap": 3e12, "trailingPE": 30, "profitMargins": 0.25,
         "returnOnEquity": 0.9, "dividendRate": 1.0}, price=200,
    )
    assert sec["הערכת שווי (Valuation)"]["מכפיל רווח נגרר (P/E)"] == "30.00"
    # dividendRate 1.0 / price 200 = 0.5%
    assert sec["דיבידנד"]["תשואת דיבידנד"] == "0.50%"
    assert app.financial_sections({}, price=None)  # no crash on empty


def test_is_crypto():
    assert app.is_crypto({"quoteType": "CRYPTOCURRENCY"}, "BTC-USD") is True
    assert app.is_crypto({}, "ETH-USD") is True
    assert app.is_crypto({"quoteType": "EQUITY"}, "AAPL") is False


def test_crypto_sections():
    cs = app.crypto_sections(
        {"marketCap": 1.3e12, "circulatingSupply": 19.7e6, "maxSupply": 21e6,
         "volume24Hr": 3e10, "algorithm": "SHA-256", "currency": "USD"}, 95000,
    )
    row = cs["נתוני מטבע"]
    assert row["היצע במחזור"] == "19.70M"
    assert row["אחוז מההיצע המרבי"] == "93.81%"


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("lang", ["he", "en"])
@pytest.mark.parametrize("ct", ["line", "candle"])
@pytest.mark.parametrize("compact", [False, True])
def test_build_chart(df_long, dark, lang, ct, compact):
    fig = app.build_chart(df_long, "TEST", dark=dark, lang=lang, chart_type=ct, compact=compact)
    assert len(fig.data) >= 5
    assert fig.layout.height == (560 if compact else 820)
    fig.to_plotly_json()  # serializes without error


def test_build_chart_short_series(df_short):
    app.build_chart(df_short, "SHORT", dark=True, lang="he").to_plotly_json()


def test_compare_row(df_long):
    r = app._compare_row(
        "TEST",
        {"marketCap": 1e12, "trailingPE": 25, "profitMargins": 0.2,
         "returnOnEquity": 0.3, "beta": 1.1, "revenueGrowth": 0.1},
        df_long, float(df_long["Close"].iloc[-1]),
    )
    assert r["סימול"] == "TEST"
    assert r["P/E"] == "25.00"
    assert r["בטא"] == "1.10"


def test_translate_offline_safe():
    # ללא רשת / כשל — חייב להחזיר מחרוזת, לעולם לא לזרוק
    out = app.maybe_he("Technology", False)
    assert out == "Technology"
    assert isinstance(app.translate_he("Technology"), str)


def test_clean_watchlist():
    assert app.clean_watchlist([" aapl ", "MSFT", "aapl", ""]) == ["AAPL", "MSFT"]
    assert app.clean_watchlist(None) == []
    assert len(app.clean_watchlist([str(i) for i in range(60)])) == 40
