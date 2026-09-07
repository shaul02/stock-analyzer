"""
מנתח מניות - אפליקציית ניתוח טכני ופיננסי מקומית
Stock Analyzer - Local Technical & Fundamental Analysis App

הכל חינמי לחלוטין:
  * הנתונים נשלפים מ-Yahoo Finance דרך הספרייה החינמית yfinance (ללא מפתח API).
  * האינדיקטורים הטכניים מחושבים עם ספריית הקוד הפתוח החינמית ta.
  * הגרפים מצוירים עם matplotlib.

הרצה:
    streamlit run app.py
"""

from __future__ import annotations

import math
import time

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator
from ta.volatility import BollingerBands

# עיצוב בסיסי: יישור מימין לשמאל לעברית, מספרים וטבלאות נשארים LTR
_PAGE_CSS = """
    <style>
      .stApp { direction: rtl; }
      .stApp h1, .stApp h2, .stApp h3, .stApp h4,
      .stApp p, .stApp label, .stApp .stMarkdown { text-align: right; }
      [data-testid="stMetric"] { direction: ltr; text-align: left; }
      .stDataFrame, [data-testid="stDataFrame"] { direction: ltr; }
    </style>
"""


# ----------------------------------------------------------------------------
# שליפת נתונים (עם מטמון של שעה כדי לא להעמיס על השרת)
# ----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_data(symbol: str, period: str, _attempts: int = 3):
    """מחזיר (DataFrame היסטורי, dict מידע על החברה).

    ל-Yahoo יש לעיתים שגיאות רשת חולפות (crumb/SSL) — מנסים שוב עד 3 פעמים.
    """
    hist = None
    last_err = None
    for i in range(_attempts):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval="1d", auto_adjust=False)
            if hist is not None and not hist.empty:
                hist = hist.dropna(subset=["Close"])
                break
        except Exception as err:  # noqa: BLE001 - כל שגיאת רשת נחשבת חולפת
            last_err = err
        time.sleep(1.5 * (i + 1))

    if hist is None or hist.empty:
        return (hist if hist is not None else None), {}, last_err

    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        info = {}

    return hist, info, None


# ----------------------------------------------------------------------------
# פונקציות פורמט
# ----------------------------------------------------------------------------
def human_number(value) -> str:
    """1234567890 -> '1.23B'."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    if value == 0 or math.isnan(value):
        return "—"
    sign = "-" if value < 0 else ""
    value = abs(value)
    for unit, factor in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if value >= factor:
            return f"{sign}{value / factor:.2f}{unit}"
    return f"{sign}{value:,.2f}"


def fmt(value, suffix: str = "", pct: bool = False, digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(num):
        return "—"
    if pct:
        return f"{num * 100:.{digits}f}%"
    return f"{num:,.{digits}f}{suffix}"


def is_num(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


# ----------------------------------------------------------------------------
# חישוב אינדיקטורים טכניים
# ----------------------------------------------------------------------------
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"]

    for window in (50, 100, 200):
        out[f"SMA{window}"] = SMAIndicator(close, window=window, fillna=False).sma_indicator()

    out["RSI"] = RSIIndicator(close, window=14, fillna=False).rsi()

    macd = MACD(close, window_slow=26, window_fast=12, window_sign=9, fillna=False)
    out["MACD"] = macd.macd()
    out["MACD_signal"] = macd.macd_signal()
    out["MACD_hist"] = macd.macd_diff()

    bb = BollingerBands(close, window=20, window_dev=2, fillna=False)
    out["BB_high"] = bb.bollinger_hband()
    out["BB_mid"] = bb.bollinger_mavg()
    out["BB_low"] = bb.bollinger_lband()

    return out


# ----------------------------------------------------------------------------
# מכפיל רווח (P/E)
# ----------------------------------------------------------------------------
def pe_ratio(info: dict, price):
    """מחזיר (ערך P/E או None, טקסט מקור)."""
    trailing = info.get("trailingPE")
    if trailing:
        return float(trailing), "trailingPE מ-yfinance"

    eps = info.get("trailingEps")
    if price and eps:
        try:
            return float(price) / float(eps), "מחושב: מחיר נוכחי חלקי EPS"
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    forward = info.get("forwardPE")
    if forward:
        return float(forward), "forwardPE מ-yfinance (מכפיל עתידי)"

    return None, "לא זמין"


# ----------------------------------------------------------------------------
# סיכום טכני אוטומטי: Bullish / Bearish / Neutral
# ----------------------------------------------------------------------------
def technical_summary(df: pd.DataFrame):
    latest = df.iloc[-1]
    price = float(latest["Close"])
    rows: list[dict] = []
    score = 0

    def add(ok, label, bull, bear, neutral=None):
        nonlocal score
        if ok is None:
            rows.append({"אינדיקטור": label, "איתות": "—", "פירוש": "אין מספיק נתונים"})
        elif ok:
            score += 1
            rows.append({"אינדיקטור": label, "איתות": "חיובי ▲", "פירוש": bull})
        elif ok is False:
            score -= 1
            rows.append({"אינדיקטור": label, "איתות": "שלילי ▼", "פירוש": bear})
        else:  # "neutral"
            rows.append({"אינדיקטור": label, "איתות": "ניטרלי ◆", "פירוש": neutral})

    sma50 = latest.get("SMA50")
    sma200 = latest.get("SMA200")
    rsi = latest.get("RSI")
    macd = latest.get("MACD")
    macd_sig = latest.get("MACD_signal")
    bb_high = latest.get("BB_high")
    bb_low = latest.get("BB_low")

    add(price > latest["SMA50"] if is_num(latest.get("SMA50")) else None,
        "מחיר מול ממוצע נע 50",
        "המחיר מעל ממוצע 50 יום", "המחיר מתחת לממוצע 50 יום")

    add(price > latest["SMA100"] if is_num(latest.get("SMA100")) else None,
        "מחיר מול ממוצע נע 100",
        "המחיר מעל ממוצע 100 יום", "המחיר מתחת לממוצע 100 יום")

    add(price > latest["SMA200"] if is_num(latest.get("SMA200")) else None,
        "מחיר מול ממוצע נע 200",
        "המחיר מעל ממוצע 200 יום — מגמה ארוכת טווח חיובית",
        "המחיר מתחת לממוצע 200 יום — מגמה ארוכת טווח שלילית")

    add(sma50 > sma200 if (is_num(sma50) and is_num(sma200)) else None,
        "צלב זהב / צלב מוות (50 מול 200)",
        "ממוצע 50 מעל ממוצע 200 — 'צלב זהב'",
        "ממוצע 50 מתחת לממוצע 200 — 'צלב מוות'")

    if is_num(rsi):
        if rsi < 30:
            score += 1
            rows.append({"אינדיקטור": f"RSI (14) = {rsi:.1f}", "איתות": "חיובי ▲",
                         "פירוש": "מכירת יתר — פוטנציאל לתיקון כלפי מעלה"})
        elif rsi > 70:
            score -= 1
            rows.append({"אינדיקטור": f"RSI (14) = {rsi:.1f}", "איתות": "שלילי ▼",
                         "פירוש": "קניית יתר — סיכון לתיקון כלפי מטה"})
        else:
            rows.append({"אינדיקטור": f"RSI (14) = {rsi:.1f}", "איתות": "ניטרלי ◆",
                         "פירוש": "בטווח מאוזן (30–70)"})
    else:
        rows.append({"אינדיקטור": "RSI (14)", "איתות": "—", "פירוש": "אין מספיק נתונים"})

    add(macd > macd_sig if (is_num(macd) and is_num(macd_sig)) else None,
        "MACD מול קו הסיגנל",
        "MACD מעל קו הסיגנל — מומנטום חיובי",
        "MACD מתחת לקו הסיגנל — מומנטום שלילי")

    if is_num(bb_high) and is_num(bb_low):
        if price > bb_high:
            score -= 1
            rows.append({"אינדיקטור": "רצועות בולינגר", "איתות": "שלילי ▼",
                         "פירוש": "המחיר מעל הרצועה העליונה — מתיחות/קניית יתר"})
        elif price < bb_low:
            score += 1
            rows.append({"אינדיקטור": "רצועות בולינגר", "איתות": "חיובי ▲",
                         "פירוש": "המחיר מתחת לרצועה התחתונה — מתיחות/מכירת יתר"})
        else:
            rows.append({"אינדיקטור": "רצועות בולינגר", "איתות": "ניטרלי ◆",
                         "פירוש": "המחיר בתוך הרצועות"})
    else:
        rows.append({"אינדיקטור": "רצועות בולינגר", "איתות": "—", "פירוש": "אין מספיק נתונים"})

    if score >= 2:
        verdict, icon, kind = "Bullish — מגמה חיובית", "🟢", "success"
    elif score <= -2:
        verdict, icon, kind = "Bearish — מגמה שלילית", "🔴", "error"
    else:
        verdict, icon, kind = "Neutral — ניטרלי", "🟡", "info"

    return verdict, icon, kind, score, pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# בניית הגרף (תוויות באנגלית כדי שכל הפונטים ירונדרו כראוי)
# ----------------------------------------------------------------------------
def build_chart(df: pd.DataFrame, symbol: str):
    plot_df = df.tail(400)

    fig, (ax_price, ax_vol, ax_rsi, ax_macd) = plt.subplots(
        4, 1, figsize=(12, 11), sharex=True,
        gridspec_kw={"height_ratios": [3, 0.8, 1, 1]},
    )

    # --- מחיר + ממוצעים נעים + בולינגר ---
    ax_price.plot(plot_df.index, plot_df["Close"], label="Close", color="#1f77b4", linewidth=1.5)
    for col, color in (("SMA50", "#ff7f0e"), ("SMA100", "#2ca02c"), ("SMA200", "#d62728")):
        if plot_df[col].notna().any():
            ax_price.plot(plot_df.index, plot_df[col], label=col, linewidth=1.1, color=color)
    if plot_df["BB_high"].notna().any():
        ax_price.plot(plot_df.index, plot_df["BB_high"], color="#9467bd", linewidth=0.8, alpha=0.6)
        ax_price.plot(plot_df.index, plot_df["BB_low"], color="#9467bd", linewidth=0.8, alpha=0.6)
        ax_price.fill_between(plot_df.index, plot_df["BB_low"], plot_df["BB_high"],
                             color="#9467bd", alpha=0.08, label="Bollinger (20,2)")
    ax_price.set_title(f"{symbol} — Price & Indicators")
    ax_price.set_ylabel("Price")
    ax_price.legend(loc="upper left", fontsize=8, ncol=2)
    ax_price.grid(alpha=0.3)

    # --- ווליום ---
    ax_vol.bar(plot_df.index, plot_df["Volume"], color="#888888", width=1.0)
    ax_vol.set_ylabel("Volume")
    ax_vol.grid(alpha=0.3)

    # --- RSI ---
    ax_rsi.plot(plot_df.index, plot_df["RSI"], color="#8c564b", linewidth=1.2)
    ax_rsi.axhline(70, color="#d62728", linestyle="--", linewidth=0.8)
    ax_rsi.axhline(30, color="#2ca02c", linestyle="--", linewidth=0.8)
    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel("RSI (14)")
    ax_rsi.grid(alpha=0.3)

    # --- MACD ---
    ax_macd.plot(plot_df.index, plot_df["MACD"], color="#1f77b4", linewidth=1.2, label="MACD")
    ax_macd.plot(plot_df.index, plot_df["MACD_signal"], color="#ff7f0e", linewidth=1.2, label="Signal")
    hist = plot_df["MACD_hist"].fillna(0)
    ax_macd.bar(plot_df.index, hist, width=1.0, alpha=0.5,
                color=["#2ca02c" if v >= 0 else "#d62728" for v in hist])
    ax_macd.axhline(0, color="black", linewidth=0.6)
    ax_macd.set_ylabel("MACD (12,26,9)")
    ax_macd.legend(loc="upper left", fontsize=8)
    ax_macd.grid(alpha=0.3)

    fig.tight_layout()
    return fig


# ----------------------------------------------------------------------------
# ממשק המשתמש
# ----------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="מנתח מניות", page_icon="📈", layout="wide")
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)

    st.title("📈 מנתח מניות — ניתוח טכני ופיננסי")
    st.caption(
        "כל הנתונים מגיעים מ-Yahoo Finance דרך הספרייה החינמית yfinance. "
        "אין צורך במפתח API ואין שום שירות בתשלום."
    )

    with st.form("analyze_form"):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            symbol_input = st.text_input(
                "סימול מניה", value="AAPL",
                placeholder="לדוגמה: AAPL, TSLA, MSFT, NVDA, GOOGL",
            )
        with c2:
            period = st.selectbox(
                "טווח נתונים", ["6mo", "1y", "2y", "5y", "10y", "max"], index=2
            )
        with c3:
            st.markdown("<div style='height:1.9em'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("🔍 נתח מניה", use_container_width=True)

    if submitted:
        st.session_state["run"] = True
        st.session_state["symbol"] = (symbol_input or "").strip().upper()
        st.session_state["period"] = period

    if not st.session_state.get("run"):
        st.info("הזן סימול מניה למעלה ולחץ על **נתח מניה**.")
        st.stop()

    symbol = st.session_state["symbol"]
    period = st.session_state["period"]

    if not symbol:
        st.warning("יש להזין סימול מניה.")
        st.stop()

    with st.spinner(f"טוען נתונים עבור {symbol}…"):
        hist, info, load_err = load_data(symbol, period)

    if hist is None or hist.empty:
        st.error(
            f"לא הצלחתי לשלוף נתונים עבור '{symbol}'.\n\n"
            "אפשרויות: הסימול שגוי / אין חיבור אינטרנט / Yahoo Finance חוסם זמנית. "
            "המתן דקה ולחץ שוב על 'נתח מניה'."
        )
        if load_err:
            st.caption(f"פרטי שגיאה: {load_err}")
        st.stop()

    df = add_indicators(hist)
    latest = df.iloc[-1]

    price = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2]) if len(df) > 1 else price
    day_change = price - prev
    day_change_pct = (day_change / prev * 100) if prev else 0.0
    start_price = float(df["Close"].iloc[0])
    period_change_pct = ((price - start_price) / start_price * 100) if start_price else 0.0

    pe, pe_source = pe_ratio(info, info.get("currentPrice") or price)
    verdict, icon, kind, score, signals_df = technical_summary(df)

    company_name = info.get("longName") or info.get("shortName") or symbol
    currency = info.get("currency", "")

    # --- שורת מדדים עליונה ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"{symbol} — מחיר אחרון", f"{price:,.2f} {currency}".strip())
    m2.metric("שינוי יומי", f"{day_change:+,.2f}", f"{day_change_pct:+.2f}%")
    m3.metric(f"שינוי בטווח ({period})", f"{period_change_pct:+.2f}%")
    m4.metric("מכפיל רווח (P/E)", fmt(pe) if pe else "—")

    if len(df) < 200:
        st.info(
            "טווח הנתונים קצר מ-200 ימי מסחר, לכן ממוצע נע 200 עשוי להיות חסר או חלקי. "
            "מומלץ לבחור טווח של שנתיים ומעלה."
        )

    tab_overview, tab_fund, tab_tech, tab_chart, tab_raw = st.tabs(
        ["🧭 סקירה כללית", "💰 נתונים פיננסיים", "📊 ניתוח טכני", "📈 גרפים", "🗂 נתונים גולמיים"]
    )

    # --- סקירה כללית ---
    with tab_overview:
        st.subheader(company_name)
        meta = " · ".join(
            p for p in [info.get("sector"), info.get("industry"), info.get("exchange")] if p
        )
        if meta:
            st.write(meta)

        getattr(st, kind)(f"{icon}  סיכום טכני אוטומטי: **{verdict}**  (ניקוד: {score:+d})")

        summary = info.get("longBusinessSummary")
        if summary:
            with st.expander("תיאור החברה"):
                st.write(summary)

    # --- נתונים פיננסיים ---
    with tab_fund:
        st.subheader("נתונים פיננסיים בסיסיים")

        fc1, fc2 = st.columns(2)
        fc1.metric("מכפיל רווח (P/E)", fmt(pe) if pe else "—")
        fc1.caption(f"מקור: {pe_source}")
        fc2.metric("שווי שוק", human_number(info.get("marketCap")))

        div_yield = info.get("dividendYield")
        fundamentals = {
            "שם החברה": company_name,
            "סקטור": info.get("sector", "—"),
            "תעשייה": info.get("industry", "—"),
            "בורסה": info.get("exchange", "—"),
            "מטבע": currency or "—",
            "מחיר נוכחי": fmt(info.get("currentPrice") or price),
            "שווי שוק": human_number(info.get("marketCap")),
            "מכפיל רווח (P/E)": fmt(pe) if pe else "—",
            "מכפיל רווח עתידי (Forward P/E)": fmt(info.get("forwardPE")),
            "מכפיל PEG": fmt(info.get("pegRatio")),
            "רווח למניה (EPS)": fmt(info.get("trailingEps")),
            "תשואת דיבידנד": fmt(div_yield, pct=True) if div_yield else "—",
            "מכפיל מחיר/מכירות (P/S)": fmt(info.get("priceToSalesTrailing12Months")),
            "מכפיל הון (P/B)": fmt(info.get("priceToBook")),
            "בטא (Beta)": fmt(info.get("beta")),
            "שיא 52 שבועות": fmt(info.get("fiftyTwoWeekHigh")),
            "שפל 52 שבועות": fmt(info.get("fiftyTwoWeekLow")),
            "מחזור מסחר ממוצע": human_number(info.get("averageVolume")),
        }
        fund_df = pd.DataFrame(
            {"פרמטר": list(fundamentals.keys()), "ערך": list(fundamentals.values())}
        )
        st.dataframe(fund_df, hide_index=True, use_container_width=True)

        if not info or len(info) < 5:
            st.warning(
                "Yahoo Finance החזיר מידע חברה חלקי או ריק עבור סימול זה. "
                "נתוני המחיר והאינדיקטורים עדיין תקינים."
            )

    # --- ניתוח טכני ---
    with tab_tech:
        getattr(st, kind)(f"{icon}  סיכום טכני אוטומטי: **{verdict}**  (ניקוד: {score:+d})")
        st.caption(
            "הניקוד מסכם את האיתותים בטבלה למטה: כל איתות חיובי מוסיף נקודה, כל שלילי מוריד. "
            "ניקוד ‎+2‎ ומעלה = Bullish, ‎−2‎ ומטה = Bearish, ביניהם = Neutral."
        )

        st.markdown("#### ערכי האינדיקטורים האחרונים")
        tech_vals = {
            "מחיר סגירה אחרון": fmt(latest["Close"]),
            "ממוצע נע 50": fmt(latest["SMA50"]),
            "ממוצע נע 100": fmt(latest["SMA100"]),
            "ממוצע נע 200": fmt(latest["SMA200"]),
            "RSI (14)": fmt(latest["RSI"]),
            "MACD": fmt(latest["MACD"], digits=3),
            "קו סיגנל MACD": fmt(latest["MACD_signal"], digits=3),
            "היסטוגרמת MACD": fmt(latest["MACD_hist"], digits=3),
            "בולינגר — עליון": fmt(latest["BB_high"]),
            "בולינגר — אמצע": fmt(latest["BB_mid"]),
            "בולינגר — תחתון": fmt(latest["BB_low"]),
        }
        tech_df = pd.DataFrame(
            {"אינדיקטור": list(tech_vals.keys()), "ערך": list(tech_vals.values())}
        )
        st.dataframe(tech_df, hide_index=True, use_container_width=True)

        st.markdown("#### פירוט האיתותים")
        st.dataframe(signals_df, hide_index=True, use_container_width=True)

    # --- גרפים ---
    with tab_chart:
        fig = build_chart(df, symbol)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
        st.caption("הגרף מציג עד 400 ימי המסחר האחרונים.")

    # --- נתונים גולמיים ---
    with tab_raw:
        st.dataframe(df.tail(300), use_container_width=True)
        csv = df.to_csv().encode("utf-8-sig")
        st.download_button(
            "⬇ הורדת כל הנתונים כקובץ CSV",
            data=csv,
            file_name=f"{symbol}_analysis.csv",
            mime="text/csv",
        )

    st.divider()
    st.caption(
        "⚠️ הכלי מיועד ללימוד ולמחקר בלבד ואינו מהווה ייעוץ השקעות, המלצה או הצעה לפעולה. "
        "נתוני Yahoo Finance עשויים להיות מושהים או לא מדויקים."
    )


if __name__ == "__main__":
    main()
