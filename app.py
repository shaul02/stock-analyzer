"""
מנתח מניות - אפליקציית ניתוח טכני ופיננסי מקומית
Stock Analyzer - Local Technical & Fundamental Analysis App

הכל חינמי לחלוטין:
  * הנתונים נשלפים מ-Yahoo Finance דרך הספרייה החינמית yfinance (ללא מפתח API).
  * האינדיקטורים הטכניים מחושבים עם ספריית הקוד הפתוח החינמית ta.
  * הגרפים מצוירים עם plotly (אינטראקטיביים, תומכים בעברית ובמצב לילה).
  * תרגום אופציונלי לעברית דרך deep-translator (שירות חינמי).

הרצה:
    streamlit run app.py
"""

from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import ADXIndicator, MACD, SMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import OnBalanceVolumeIndicator

# עיצוב בסיסי: יישור מימין לשמאל לעברית.
# חשוב: לא לגעת ב-.stApp / stAppViewContainer עצמם — RTL עליהם שובר את
# אנימציית פתיחה/סגירה של סרגל הצד. מחילים RTL רק על תוכן הראשי ותוכן הסיידבר.
_BASE_CSS = """
      [data-testid="stMain"], section.main, .main { direction: rtl; }
      [data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3,
      [data-testid="stMain"] h4, [data-testid="stMain"] p, [data-testid="stMain"] label,
      [data-testid="stMain"] .stMarkdown { text-align: right; }
      [data-testid="stMetric"] { direction: ltr; text-align: left; }
      [data-testid="stTable"], [data-testid="stDataFrame"] { direction: ltr; }
      [data-testid="stSidebarUserContent"] { direction: rtl; text-align: right; }
"""

# שכבת מצב לילה — נדרסת רק כשהמשתמש מדליק אותה
_DARK_CSS = """
      :root, .stApp { color-scheme: dark; }
      .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
          background-color: #0e1117 !important; }
      [data-testid="stSidebar"] { background-color: #161a23 !important; }
      .stApp, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5,
      .stApp p, .stApp label, .stApp span, .stApp li, .stApp .stMarkdown,
      [data-testid="stMetricValue"], [data-testid="stMetricLabel"],
      .stTabs [data-baseweb="tab"] { color: #e6e6e6 !important; }
      [data-testid="stTable"] table { color: #e6e6e6 !important; }
      [data-testid="stTable"] th, [data-testid="stTable"] td {
          border-color: #2a2f3a !important; }
      [data-testid="stDataFrame"] { filter: invert(0.92) hue-rotate(180deg); }
      /* שדות קלט וכפתורים */
      [data-testid="stTextInput"] input, [data-baseweb="select"] > div,
      [data-baseweb="input"], [data-baseweb="base-input"] {
          background-color: #1c212b !important; color: #e6e6e6 !important;
          border-color: #2a2f3a !important; }
      [data-testid="stTextInput"] input::placeholder { color: #8a93a3 !important; }
      [data-testid="baseButton-secondary"], [data-testid="stFormSubmitButton"] button {
          background-color: #1c212b !important; color: #e6e6e6 !important;
          border-color: #2a2f3a !important; }
      [data-testid="stExpander"] { border-color: #2a2f3a !important; }
      /* כפתור פתיחת סרגל הצד כשהוא מכווץ — שיישאר גלוי במצב לילה */
      [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],
      [data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"] svg,
      [data-testid="stSidebarCollapseButton"] svg { color: #e6e6e6 !important; fill: #e6e6e6 !important; }
"""


def _page_css(dark: bool) -> str:
    return f"<style>{_BASE_CSS}{_DARK_CSS if dark else ''}</style>"


# ----------------------------------------------------------------------------
# פענוח שם חברה -> סימול (כדי לקבל גם "NVIDIA" ולא רק "NVDA")
# משתמש בנקודת החיפוש הציבורית והחינמית של Yahoo (ללא מפתח).
# ----------------------------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def resolve_symbol(query: str):
    """מחזיר (symbol, shortname) עבור טקסט חופשי, או (None, None) אם לא נמצא."""
    q = (query or "").strip()
    if not q:
        return None, None
    url = "https://query2.finance.yahoo.com/v1/finance/search?" + urllib.parse.urlencode(
        {"q": q, "quotesCount": 5, "newsCount": 0}
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data.get("quotes", []):
            sym = item.get("symbol")
            if sym and item.get("quoteType") in (None, "EQUITY", "ETF", "INDEX", "CRYPTOCURRENCY", "MUTUALFUND"):
                return sym, item.get("shortname") or item.get("longname")
        if data.get("quotes"):
            first = data["quotes"][0]
            return first.get("symbol"), first.get("shortname")
    except Exception:
        pass
    return None, None


# ----------------------------------------------------------------------------
# שליפת נתונים (עם מטמון של שעה כדי לא להעמיס על השרת)
# ----------------------------------------------------------------------------
def _fetch_history(symbol: str, period: str, attempts: int = 3):
    """מחזיר (DataFrame או None, שגיאה אחרונה). מנסה שוב על שגיאות רשת חולפות."""
    hist, last_err = None, None
    for i in range(attempts):
        try:
            hist = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=False)
            if hist is not None and not hist.empty:
                return hist.dropna(subset=["Close"]), None
        except Exception as err:  # noqa: BLE001 - כל שגיאת רשת נחשבת חולפת
            last_err = err
        time.sleep(1.5 * (i + 1))
    return (hist if hist is not None else None), last_err


_PERIOD_DAYS = {"6mo": 190, "1y": 380, "2y": 760, "5y": 1850, "10y": 3700, "max": 12000}


def _fetch_stooq(symbol: str, period: str):
    """מקור מחיר עצמאי וחינמי (Stooq) — משמש כגיבוי כש-Yahoo לא זמין."""
    sym = symbol.lower().strip()
    candidates = [sym] if "." in sym else [f"{sym}.us", sym]
    for cand in candidates:
        url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(cand)}&i=d"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
            if not raw.startswith("Date"):
                continue
            from io import StringIO

            df = pd.read_csv(StringIO(raw), parse_dates=["Date"]).set_index("Date")
            df = df.rename(columns=str.capitalize)
            if df.empty or "Close" not in df:
                continue
            df = df.dropna(subset=["Close"]).tail(_PERIOD_DAYS.get(period, 760))
            if "Volume" not in df:
                df["Volume"] = 0
            return df[["Open", "High", "Low", "Close", "Volume"]], None
        except Exception as err:  # noqa: BLE001
            last = err
    return None, locals().get("last")


@st.cache_data(ttl=3600, show_spinner=False)
def load_data(symbol: str, period: str):
    """מחזיר (hist, info, err, used_symbol, resolved_name, price_source).

    אם הסימול שהוזן לא קיים, מנסה לפענח שם חברה (למשל 'NVIDIA' -> 'NVDA').
    אם Yahoo לא מחזיר מחירים — נופל ל-Stooq.
    """
    used = (symbol or "").strip().upper()
    price_source = "Yahoo Finance"
    hist, err = _fetch_history(used, period)

    resolved_name = None

    # אולי הוזן סימול קריפטו בלי הסיומת (BTC -> BTC-USD)
    if (hist is None or hist.empty) and used and used.isalnum() and len(used) <= 5:
        hist_c, _ = _fetch_history(f"{used}-USD", period)
        if hist_c is not None and not hist_c.empty:
            used, hist, err = f"{used}-USD", hist_c, None

    if hist is None or hist.empty:
        alt_sym, alt_name = resolve_symbol(symbol)
        if alt_sym and alt_sym.upper() != used:
            hist2, _ = _fetch_history(alt_sym, period)
            if hist2 is not None and not hist2.empty:
                used, hist, err, resolved_name = alt_sym.upper(), hist2, None, alt_name

    if hist is None or hist.empty:
        stooq_hist, stooq_err = _fetch_stooq(used, period)
        if stooq_hist is not None and not stooq_hist.empty:
            hist, err, price_source = stooq_hist, None, "Stooq"
        else:
            return None, {}, err or stooq_err, used, None, None

    try:
        info = yf.Ticker(used).info or {}
    except Exception:
        info = {}

    return hist, info, None, used, resolved_name, price_source


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


_CCY = {
    "USD": "$", "EUR": "€", "GBP": "£", "GBp": "p", "ILS": "₪", "ILA": "₪",
    "JPY": "¥", "CNY": "¥", "HKD": "HK$", "CAD": "C$", "AUD": "A$", "NZD": "NZ$",
    "CHF": "CHF ", "INR": "₹", "KRW": "₩", "BRL": "R$", "SEK": "kr ", "NOK": "kr ",
    "DKK": "kr ", "ZAR": "R ", "MXN": "MX$", "SGD": "S$", "TWD": "NT$", "TRY": "₺",
}


def ccy_sym(code: str) -> str:
    if not code:
        return ""
    return _CCY.get(code, f"{code} ")


def price_str(value, code: str = "", digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        return f"{ccy_sym(code)}{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


# ----------------------------------------------------------------------------
# תרגום אופציונלי לעברית (שירות חינמי, ללא מפתח). נכשל בשקט -> מחזיר מקור.
# ----------------------------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def translate_he(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    try:
        from deep_translator import GoogleTranslator

        out = GoogleTranslator(source="auto", target="iw").translate(text[:4800])
        if not out:
            return text
        low = out.lower()
        if any(b in low for b in ("that’s an error", "that's an error", "error 500",
                                  "<html", "server error")):
            return text  # השירות החינמי החזיר דף שגיאה — נשארים עם המקור
        return out
    except Exception:
        return text


def maybe_he(text, enabled: bool):
    """מתרגם רק אם המתג דלוק ויש טקסט לא-ריק."""
    if enabled and text:
        return translate_he(str(text))
    return text


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

    # אינדיקטורים נוספים — דורשים High/Low/Volume
    if {"High", "Low"}.issubset(out.columns):
        high, low = out["High"], out["Low"]
        try:
            out["ATR"] = AverageTrueRange(high, low, close, window=14, fillna=False).average_true_range()
            out["ATR_pct"] = out["ATR"] / close * 100
        except Exception:
            pass
        try:
            out["ADX"] = ADXIndicator(high, low, close, window=14, fillna=False).adx()
        except Exception:
            pass
        try:
            stoch = StochasticOscillator(high, low, close, window=14, smooth_window=3, fillna=False)
            out["STOCH_K"] = stoch.stoch()
            out["STOCH_D"] = stoch.stoch_signal()
        except Exception:
            pass
    if "Volume" in out.columns and out["Volume"].fillna(0).abs().sum() > 0:
        try:
            out["OBV"] = OnBalanceVolumeIndicator(close, out["Volume"], fillna=False).on_balance_volume()
        except Exception:
            pass

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
# נתונים פיננסיים מורחבים מ-yfinance (הרבה מעבר לכמה מכפילים)
# ----------------------------------------------------------------------------
def financial_sections(info: dict, price=None) -> dict:
    """מחזיר dict מסודר: {שם קטגוריה: {תווית: ערך מוכן לתצוגה}}."""
    g = info.get

    def money(key):
        return human_number(g(key))

    def num(key, digits=2, suffix=""):
        return fmt(g(key), suffix=suffix, digits=digits)

    def pct(key, digits=2):
        v = g(key)
        return fmt(v, pct=True, digits=digits) if v is not None else "—"

    def _pct_frac(v):
        """מנרמל ערך אחוז לשבר: 2.4 -> 0.024, 0.024 -> 0.024 (הגנה מפני שינויי פורמט ב-yfinance)."""
        if v is None:
            return None
        return v / 100 if abs(v) > 1 else v

    # תשואת דיבידנד: מחשבים מ-dividendRate/מחיר כשאפשר (יחידות מטבע אמינות),
    # אחרת מנרמלים את dividendYield שהפורמט שלו השתנה בין גרסאות yfinance.
    dr = g("dividendRate")
    if dr and price:
        div_yield_frac = dr / price
    else:
        div_yield_frac = _pct_frac(g("dividendYield"))
    div_5y = _pct_frac(g("fiveYearAvgDividendYield"))

    fcf = g("freeCashflow")
    mcap = g("marketCap")
    p_fcf = fmt(mcap / fcf) if (mcap and fcf) else "—"

    return {
        "הערכת שווי (Valuation)": {
            "שווי שוק": money("marketCap"),
            "שווי מיזם (EV)": money("enterpriseValue"),
            "מכפיל רווח נגרר (P/E)": num("trailingPE"),
            "מכפיל רווח עתידי (Fwd P/E)": num("forwardPE"),
            "מכפיל PEG": num("trailingPegRatio") if g("trailingPegRatio") else num("pegRatio"),
            "מחיר / מכירות (P/S)": num("priceToSalesTrailing12Months"),
            "מחיר / הון עצמי (P/B)": num("priceToBook"),
            "EV / EBITDA": num("enterpriseToEbitda"),
            "EV / הכנסות": num("enterpriseToRevenue"),
            "מחיר / תזרים חופשי (P/FCF)": p_fcf,
        },
        "רווחיות (Profitability)": {
            "שולי רווח גולמי": pct("grossMargins"),
            "שולי רווח תפעולי": pct("operatingMargins"),
            "שולי רווח נקי": pct("profitMargins"),
            "שולי EBITDA": pct("ebitdaMargins"),
            "תשואה על ההון (ROE)": pct("returnOnEquity"),
            "תשואה על הנכסים (ROA)": pct("returnOnAssets"),
        },
        "צמיחה (Growth)": {
            "צמיחת הכנסות (שנתי)": pct("revenueGrowth"),
            "צמיחת רווח (שנתי)": pct("earningsGrowth"),
            "צמיחת רווח רבעוני (YoY)": pct("earningsQuarterlyGrowth"),
            "הכנסות 12 חודשים": money("totalRevenue"),
            "רווח נקי (12 ח')": money("netIncomeToCommon"),
            "EBITDA": money("ebitda"),
        },
        "איתנות פיננסית (Balance Sheet)": {
            "מזומן ושווי מזומן": money("totalCash"),
            "חוב כולל": money("totalDebt"),
            "חוב נטו": human_number((g("totalDebt") or 0) - (g("totalCash") or 0))
            if (g("totalDebt") or g("totalCash")) else "—",
            "יחס חוב להון (D/E)": num("debtToEquity"),
            "יחס שוטף (Current)": num("currentRatio"),
            "יחס מהיר (Quick)": num("quickRatio"),
            "מזומן למניה": num("totalCashPerShare"),
            "תזרים חופשי (FCF)": money("freeCashflow"),
            "תזרים תפעולי": money("operatingCashflow"),
        },
        "דיבידנד": {
            "דיבידנד למניה (שנתי)": num("dividendRate"),
            "תשואת דיבידנד": fmt(div_yield_frac, pct=True) if div_yield_frac is not None else "—",
            "תשואה ממוצעת 5 שנים": fmt(div_5y, pct=True) if div_5y is not None else "—",
            "יחס חלוקה (Payout)": pct("payoutRatio"),
        },
        "תחזית אנליסטים": {
            "המלצה": str(g("recommendationKey") or "—").upper(),
            "מספר אנליסטים": num("numberOfAnalystOpinions", digits=0),
            "מחיר יעד ממוצע": num("targetMeanPrice"),
            "מחיר יעד גבוה": num("targetHighPrice"),
            "מחיר יעד נמוך": num("targetLowPrice"),
            "פוטנציאל מול מחיר נוכחי":
                fmt((g("targetMeanPrice") / price - 1), pct=True)
                if (g("targetMeanPrice") and price) else "—",
        },
        "מניה ומסחר": {
            "מניות במחזור": money("sharesOutstanding"),
            "מניות חופשיות (Float)": money("floatShares"),
            "אחזקת מוסדיים": pct("heldPercentInstitutions"),
            "פוזיציות שורט (% מ-Float)": pct("shortPercentOfFloat"),
            "בטא (Beta)": num("beta"),
            "טווח 52 שבועות": f'{fmt(g("fiftyTwoWeekLow"))} – {fmt(g("fiftyTwoWeekHigh"))}',
            "מחזור מסחר ממוצע": money("averageVolume"),
        },
    }


def is_crypto(info: dict, symbol: str = "") -> bool:
    return (info.get("quoteType") or "").upper() == "CRYPTOCURRENCY" or \
        symbol.upper().endswith(("-USD", "-EUR", "-USDT"))


def crypto_sections(info: dict, price=None) -> dict:
    """סעיפי מידע רלוונטיים למטבע קריפטו (במקום נתוני יסוד של חברה)."""
    g = info.get
    supply = g("circulatingSupply")
    max_supply = g("maxSupply") or g("totalSupply")
    return {
        "נתוני מטבע": {
            "שווי שוק": human_number(g("marketCap")),
            "היצע במחזור": human_number(supply),
            "היצע מרבי / כולל": human_number(max_supply),
            "אחוז מההיצע המרבי":
                fmt(supply / max_supply, pct=True) if (supply and max_supply) else "—",
            "נפח מסחר 24 שעות":
                human_number(g("volume24Hr") or g("regularMarketVolume") or g("volume")),
            "מטבע התייחסות": g("currency") or "USD",
            "אלגוריתם": g("algorithm") or "—",
            "טווח 52 שבועות":
                f'{fmt(g("fiftyTwoWeekLow"))} – {fmt(g("fiftyTwoWeekHigh"))}',
        }
    }


@st.cache_data(ttl=3600, show_spinner=False)
def get_statements(symbol: str) -> dict:
    """דוחות כספיים (שנתי + רבעוני) מ-yfinance. dict של DataFrames, ריק אם אין."""
    out = {}
    try:
        tk = yf.Ticker(symbol)
        pairs = {
            "דוח רווח והפסד (שנתי)": "income_stmt",
            "דוח רווח והפסד (רבעוני)": "quarterly_income_stmt",
            "מאזן (שנתי)": "balance_sheet",
            "מאזן (רבעוני)": "quarterly_balance_sheet",
            "תזרים מזומנים (שנתי)": "cashflow",
            "תזרים מזומנים (רבעוני)": "quarterly_cashflow",
        }
        for label, attr in pairs.items():
            try:
                df = getattr(tk, attr)
                if df is not None and not df.empty:
                    df = df.copy()
                    df.columns = [str(c)[:10] for c in df.columns]
                    out[label] = df
            except Exception:
                continue
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------------
# מקור עצמאי #2: SEC EDGAR — דוחות רשמיים מוגשים (חינמי לגמרי, ללא מפתח).
# רלוונטי לחברות אמריקאיות בלבד.
# ----------------------------------------------------------------------------
_SEC_UA = {"User-Agent": "stock-analyzer educational project contact@example.com"}
# (תווית, [מפתחות us-gaap אפשריים], instant?) — instant=מאזן (ערך רגעי), אחרת "זרימה" שנתית
_SEC_CONCEPTS = [
    ("הכנסות", ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"], False),
    ("רווח נקי", ["NetIncomeLoss", "ProfitLoss"], False),
    ("רווח תפעולי", ["OperatingIncomeLoss"], False),
    ("סך נכסים", ["Assets"], True),
    ("סך התחייבויות", ["Liabilities"], True),
    ("הון עצמי", ["StockholdersEquity",
                  "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"], True),
    ("רווח למניה מדולל", ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"], False),
]


@st.cache_data(ttl=86400, show_spinner=False)
def _sec_ticker_map() -> dict:
    try:
        req = urllib.request.Request("https://www.sec.gov/files/company_tickers.json", headers=_SEC_UA)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        return {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in raw.values()}
    except Exception:
        return {}


@st.cache_data(ttl=86400, show_spinner=False)
def get_sec_facts(symbol: str):
    """מחזיר (DataFrame שנתי לפי שנה, note). DataFrame ריק אם לא רלוונטי/נכשל."""
    cik = _sec_ticker_map().get((symbol or "").upper())
    if not cik:
        return pd.DataFrame(), "לא נמצאה חברה אמריקאית תואמת ב-SEC EDGAR (רלוונטי למניות בארה\"ב)."
    try:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        req = urllib.request.Request(url, headers=_SEC_UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            facts = json.loads(resp.read().decode("utf-8")).get("facts", {}).get("us-gaap", {})
    except Exception as err:  # noqa: BLE001
        return pd.DataFrame(), f"קריאת SEC EDGAR נכשלה: {err}"

    def _annual_by_year(concept: dict, instant: bool) -> dict:
        # year -> (fy-of-filing, value); שנה מפתח = שנת סוף התקופה
        picked: dict[int, tuple] = {}
        for entries in concept.get("units", {}).values():
            for e in entries:
                if e.get("form") not in ("10-K", "20-F"):
                    continue
                end = e.get("end")
                start = e.get("start")
                if not end:
                    continue
                try:
                    end_ts = pd.Timestamp(end)
                except Exception:
                    continue
                if instant:
                    if start:  # רוצים ערך רגעי (מאזן), לא טווח
                        continue
                else:
                    if not start:
                        continue
                    try:
                        days = (end_ts - pd.Timestamp(start)).days
                    except Exception:
                        continue
                    if not (300 <= days <= 400):  # שנה מלאה בלבד
                        continue
                yr = end_ts.year
                fyf = e.get("fy") or 0
                if yr not in picked or fyf >= picked[yr][0]:
                    picked[yr] = (fyf, e.get("val"))
        return {yr: v for yr, (_, v) in picked.items()}

    rows = {}
    for he_label, keys, instant in _SEC_CONCEPTS:
        best, best_score = {}, (-1, -1)
        for k in keys:
            if k not in facts:
                continue
            cand = _annual_by_year(facts[k], instant)
            if not cand:
                continue
            score = (max(cand), len(cand))  # מעדיפים concept עם השנה העדכנית ביותר
            if score > best_score:
                best, best_score = cand, score
        for yr, val in best.items():
            rows.setdefault(yr, {})[he_label] = val

    # השלמה: אם חסרות "סך התחייבויות" אך יש נכסים והון — נגזור
    for yr, r in rows.items():
        if r.get("סך התחייבויות") is None and r.get("סך נכסים") and r.get("הון עצמי"):
            r["סך התחייבויות"] = r["סך נכסים"] - r["הון עצמי"]

    if not rows:
        return pd.DataFrame(), "SEC EDGAR: לא נמצאו נתוני דוח שנתי במבנה צפוי."

    years = sorted(rows)[-6:]
    table = pd.DataFrame(
        {str(y): rows[y] for y in years},
        index=[lbl for lbl, _, _ in _SEC_CONCEPTS],
    )
    return table, f"מקור: SEC EDGAR · CIK {cik} · דוחות 10-K/20-F רשמיים."


# ----------------------------------------------------------------------------
# חדשות + לוח אירועים (yfinance, חינמי)
# ----------------------------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def get_news(symbol: str, limit: int = 6) -> list:
    try:
        raw = yf.Ticker(symbol).news or []
    except Exception:
        return []
    items = []
    for it in raw:
        c = it.get("content") if isinstance(it.get("content"), dict) else it
        title = c.get("title") or it.get("title")
        if not title:
            continue
        link = ""
        for k in ("canonicalUrl", "clickThroughUrl"):
            v = c.get(k)
            if isinstance(v, dict) and v.get("url"):
                link = v["url"]
                break
        link = link or it.get("link", "")
        pub = ""
        prov = c.get("provider")
        if isinstance(prov, dict):
            pub = prov.get("displayName", "")
        pub = pub or it.get("publisher", "")
        ts = c.get("pubDate") or c.get("displayTime") or it.get("providerPublishTime")
        when = ""
        try:
            if isinstance(ts, (int, float)):
                when = pd.to_datetime(ts, unit="s").strftime("%Y-%m-%d")
            elif isinstance(ts, str):
                when = ts[:10]
        except Exception:
            pass
        items.append({"title": title, "link": link, "publisher": pub, "when": when})
        if len(items) >= limit:
            break
    return items


@st.cache_data(ttl=3600, show_spinner=False)
def get_calendar_info(symbol: str) -> dict:
    try:
        cal = yf.Ticker(symbol).calendar
    except Exception:
        return {}
    out = {}
    if isinstance(cal, dict):
        ed = cal.get("Earnings Date")
        if isinstance(ed, (list, tuple)) and ed:
            out["earnings_date"] = str(ed[0])[:10]
        elif ed:
            out["earnings_date"] = str(ed)[:10]
        if cal.get("Ex-Dividend Date"):
            out["ex_div"] = str(cal["Ex-Dividend Date"])[:10]
    elif cal is not None and getattr(cal, "empty", True) is False:
        try:
            out["earnings_date"] = str(cal.iloc[0, 0])[:10]
        except Exception:
            pass
    return out


# ----------------------------------------------------------------------------
# רשימת מעקב — פר-משתמש, ב-session_state בלבד (בטוח לאפליקציה ציבורית משותפת;
# נשמרת כל עוד הכרטיסייה פתוחה, לא מסונכרנת בין מבקרים).
# ----------------------------------------------------------------------------
def clean_watchlist(items) -> list:
    return list(dict.fromkeys(str(x).strip().upper() for x in (items or []) if str(x).strip()))[:40]


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

    stoch_k = latest.get("STOCH_K")
    if is_num(stoch_k):
        if stoch_k < 20:
            score += 1
            rows.append({"אינדיקטור": f"סטוכסטי %K = {stoch_k:.0f}", "איתות": "חיובי ▲",
                         "פירוש": "מכירת יתר (מתחת ל-20)"})
        elif stoch_k > 80:
            score -= 1
            rows.append({"אינדיקטור": f"סטוכסטי %K = {stoch_k:.0f}", "איתות": "שלילי ▼",
                         "פירוש": "קניית יתר (מעל 80)"})
        else:
            rows.append({"אינדיקטור": f"סטוכסטי %K = {stoch_k:.0f}", "איתות": "ניטרלי ◆",
                         "פירוש": "בטווח מאוזן (20–80)"})

    adx = latest.get("ADX")
    if is_num(adx):
        strength = "מגמה חזקה" if adx >= 25 else ("מגמה חלשה/דשדוש" if adx < 20 else "מגמה מתגבשת")
        rows.append({"אינדיקטור": f"ADX (14) = {adx:.0f}", "איתות": "מידע",
                     "פירוש": f"{strength} — ADX מודד עוצמת מגמה, לא כיוון"})

    atr_pct = latest.get("ATR_pct")
    if is_num(atr_pct):
        rows.append({"אינדיקטור": f"ATR = {atr_pct:.1f}% מהמחיר", "איתות": "מידע",
                     "פירוש": "תנודתיות יומית ממוצעת — שימושי לתמחור סטופ-לוס"})

    if score >= 2:
        verdict, icon, kind = "מגמה חיובית (Bullish)", "🟢", "success"
    elif score <= -2:
        verdict, icon, kind = "מגמה שלילית (Bearish)", "🔴", "error"
    else:
        verdict, icon, kind = "ניטרלי (Neutral)", "🟡", "info"

    return verdict, icon, kind, score, pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# תבנית כדאיות קנייה לפי טווח (קצר / בינוני / ארוך)
# סיכום כלל-אצבע אוטומטי של האיתותים — אינו ייעוץ השקעות!
# ----------------------------------------------------------------------------
def _series_change(series: pd.Series, lookback: int):
    """שינוי באחוזים על פני `lookback` ברים אחרונים, או None אם אין מספיק נתונים."""
    s = series.dropna()
    if len(s) <= lookback or s.iloc[-1 - lookback] == 0:
        return None
    return (s.iloc[-1] / s.iloc[-1 - lookback] - 1) * 100


def _slope(series: pd.Series, lookback: int):
    """כיוון הממוצע: חיובי אם עלה על פני `lookback` ברים, שלילי אם ירד."""
    s = series.dropna()
    if len(s) <= lookback:
        return None
    return s.iloc[-1] - s.iloc[-1 - lookback]


def _label(score: int):
    if score >= 2:
        return "חיובי", "▲", "🟢"
    if score <= -2:
        return "שלילי", "▼", "🔴"
    return "ניטרלי", "◆", "🟡"


def _horizon_short(df: pd.DataFrame):
    """טווח קצר (ימים עד שבועות ספורים) — מומנטום ותנודתיות."""
    latest = df.iloc[-1]
    price = float(latest["Close"])
    reasons, score = [], 0

    bb_mid = latest.get("BB_mid")  # ממוצע 20 יום
    if is_num(bb_mid):
        if price > bb_mid:
            score += 1
            reasons.append(("המחיר מעל ממוצע 20 יום", "▲"))
        else:
            score -= 1
            reasons.append(("המחיר מתחת לממוצע 20 יום", "▼"))

    hist = df["MACD_hist"].dropna()
    if len(hist) >= 2:
        if hist.iloc[-1] > 0 and hist.iloc[-1] >= hist.iloc[-2]:
            score += 1
            reasons.append(("מומנטום MACD חיובי ומתחזק", "▲"))
        elif hist.iloc[-1] < 0 and hist.iloc[-1] <= hist.iloc[-2]:
            score -= 1
            reasons.append(("מומנטום MACD שלילי ומתחזק כלפי מטה", "▼"))
        else:
            reasons.append(("מומנטום MACD מעורב", "◆"))

    rsi = latest.get("RSI")
    if is_num(rsi):
        if rsi < 30:
            score += 1
            reasons.append((f"RSI = {rsi:.0f} — מכירת יתר, אפשרות לתיקון מעלה", "▲"))
        elif rsi > 70:
            score -= 1
            reasons.append((f"RSI = {rsi:.0f} — קניית יתר, סיכון לתיקון מטה", "▼"))
        elif rsi >= 50:
            score += 1
            reasons.append((f"RSI = {rsi:.0f} — חיובי בלי קיצון", "▲"))
        else:
            reasons.append((f"RSI = {rsi:.0f} — חלש", "◆"))

    chg5 = _series_change(df["Close"], 5)
    if chg5 is not None:
        if chg5 > 2:
            score += 1
            reasons.append((f"עלייה של {chg5:+.1f}% ב-5 ימי מסחר אחרונים", "▲"))
        elif chg5 < -2:
            score -= 1
            reasons.append((f"ירידה של {chg5:+.1f}% ב-5 ימי מסחר אחרונים", "▼"))

    bb_high, bb_low = latest.get("BB_high"), latest.get("BB_low")
    if is_num(bb_high) and is_num(bb_low) and bb_high > bb_low:
        pctb = (price - bb_low) / (bb_high - bb_low)
        if pctb < 0.2:
            score += 1
            reasons.append(("המחיר קרוב לרצועת בולינגר התחתונה", "▲"))
        elif pctb > 0.9:
            score -= 1
            reasons.append(("המחיר קרוב לרצועת בולינגר העליונה", "▼"))

    return score, reasons


def _horizon_medium(df: pd.DataFrame):
    """טווח בינוני (שבועות עד מספר חודשים) — מגמה נוכחית."""
    latest = df.iloc[-1]
    price = float(latest["Close"])
    reasons, score = [], 0

    for win in (50, 100):
        sma = latest.get(f"SMA{win}")
        if is_num(sma):
            if price > sma:
                score += 1
                reasons.append((f"המחיר מעל ממוצע {win} יום", "▲"))
            else:
                score -= 1
                reasons.append((f"המחיר מתחת לממוצע {win} יום", "▼"))

    sl = _slope(df["SMA50"], 10)
    if sl is not None:
        if sl > 0:
            score += 1
            reasons.append(("ממוצע 50 יום במגמת עלייה", "▲"))
        else:
            score -= 1
            reasons.append(("ממוצע 50 יום במגמת ירידה", "▼"))

    sma50, sma100 = latest.get("SMA50"), latest.get("SMA100")
    if is_num(sma50) and is_num(sma100):
        if sma50 > sma100:
            score += 1
            reasons.append(("ממוצע 50 מעל ממוצע 100", "▲"))
        else:
            score -= 1
            reasons.append(("ממוצע 50 מתחת לממוצע 100", "▼"))

    macd = latest.get("MACD")
    if is_num(macd):
        if macd > 0:
            score += 1
            reasons.append(("MACD מעל קו האפס", "▲"))
        else:
            score -= 1
            reasons.append(("MACD מתחת לקו האפס", "▼"))

    chg21 = _series_change(df["Close"], 21)
    if chg21 is not None:
        if chg21 > 3:
            score += 1
            reasons.append((f"עלייה של {chg21:+.1f}% בחודש האחרון", "▲"))
        elif chg21 < -3:
            score -= 1
            reasons.append((f"ירידה של {chg21:+.1f}% בחודש האחרון", "▼"))

    return score, reasons


def _horizon_long(df: pd.DataFrame, info: dict, pe):
    """טווח ארוך (מספר חודשים עד שנים) — מגמת-על והערכת שווי."""
    latest = df.iloc[-1]
    price = float(latest["Close"])
    reasons, score = [], 0

    sma200 = latest.get("SMA200")
    if is_num(sma200):
        if price > sma200:
            score += 1
            reasons.append(("המחיר מעל ממוצע 200 יום", "▲"))
        else:
            score -= 1
            reasons.append(("המחיר מתחת לממוצע 200 יום", "▼"))
        if price > sma200 * 1.4:
            score -= 1
            reasons.append(("המחיר מתוח מאוד מעל ממוצע 200 יום (סיכון תיקון)", "▼"))

    sma50 = latest.get("SMA50")
    if is_num(sma50) and is_num(sma200):
        if sma50 > sma200:
            score += 1
            reasons.append(("'צלב זהב' — ממוצע 50 מעל ממוצע 200", "▲"))
        else:
            score -= 1
            reasons.append(("'צלב מוות' — ממוצע 50 מתחת לממוצע 200", "▼"))

    sl = _slope(df["SMA200"], 21)
    if sl is not None:
        if sl > 0:
            score += 1
            reasons.append(("ממוצע 200 יום במגמת עלייה", "▲"))
        else:
            score -= 1
            reasons.append(("ממוצע 200 יום במגמת ירידה", "▼"))

    hi = info.get("fiftyTwoWeekHigh")
    lo = info.get("fiftyTwoWeekLow")
    if is_num(hi) and hi and price >= hi * 0.85:
        score += 1
        reasons.append(("קרוב לשיא 52 שבועות — מגמה חזקה", "▲"))
    elif is_num(lo) and lo and price <= lo * 1.1:
        score -= 1
        reasons.append(("קרוב לשפל 52 שבועות — חולשה", "▼"))

    if pe is not None:
        if pe <= 0:
            score -= 1
            reasons.append(("החברה מפסידה (P/E שלילי)", "▼"))
        elif pe <= 25:
            score += 1
            reasons.append((f"מכפיל רווח סביר (P/E ≈ {pe:.0f})", "▲"))
        elif pe <= 40:
            reasons.append((f"מכפיל רווח גבוה (P/E ≈ {pe:.0f})", "◆"))
        else:
            score -= 1
            reasons.append((f"מכפיל רווח גבוה מאוד (P/E ≈ {pe:.0f})", "▼"))

    peg = info.get("pegRatio")
    if is_num(peg):
        if 0 < peg < 1:
            score += 1
            reasons.append((f"PEG ≈ {peg:.2f} — צמיחה אטרקטיבית מול המחיר", "▲"))
        elif peg > 2.5:
            score -= 1
            reasons.append((f"PEG ≈ {peg:.2f} — יקר יחסית לצמיחה", "▼"))

    return score, reasons


HORIZON_META = {
    "קצר": "ימים עד שבועות ספורים",
    "בינוני": "שבועות עד מספר חודשים",
    "ארוך": "מספר חודשים עד שנים",
}


def buy_recommendation(df: pd.DataFrame, info: dict, pe):
    """מחזיר dict עם פסק כללי + פירוט לכל טווח. סיכום אוטומטי, לא ייעוץ."""
    horizons = {}
    for name, (sc, reasons) in {
        "קצר": _horizon_short(df),
        "בינוני": _horizon_medium(df),
        "ארוך": _horizon_long(df, info, pe),
    }.items():
        text, arrow, dot = _label(sc)
        horizons[name] = {
            "label": text, "arrow": arrow, "dot": dot,
            "score": sc, "reasons": reasons,
            "range": HORIZON_META[name],
        }

    positives = [n for n, h in horizons.items() if h["label"] == "חיובי"]
    negatives = [n for n, h in horizons.items() if h["label"] == "שלילי"]

    if positives:
        answer = "כן — האיתותים תומכים בקנייה"
        kind = "success"
        horizon_txt = "טווח " + " + ".join(positives)
    elif negatives and not positives:
        answer = "לא כרגע — האיתותים הטכניים שליליים"
        kind = "error"
        horizon_txt = "—"
    else:
        answer = "לא חד-משמעי — עדיף להמתין לאיתות ברור"
        kind = "info"
        horizon_txt = "—"

    return {
        "answer": answer,
        "kind": kind,
        "horizon_txt": horizon_txt,
        "positives": positives,
        "horizons": horizons,
    }


# ----------------------------------------------------------------------------
# בדיקה היסטורית (בקטסט) של איתות המגמה — עד כמה הוא "היה עובד" בעבר
# ----------------------------------------------------------------------------
def backtest_signal(df: pd.DataFrame, fwd: int = 20):
    """גרסה וקטורית של ניקוד הטווח-הבינוני, מיושמת יום-אחר-יום (walk-forward).

    לונג כשהניקוד ‎+2‎ ומעלה, מחוץ לשוק כשהניקוד ‎−2‎ ומטה, אחרת מחזיקים מצב קודם.
    לא מנצל מידע עתידי (כל שורה משתמשת רק בנתונים שהיו זמינים באותו יום).
    """
    d = df.dropna(subset=["Close"]).copy()
    if len(d) < 160:
        return None

    c = d["Close"]
    sma50, sma100 = d["SMA50"], d["SMA100"]
    macd = d.get("MACD")

    s = (
        (c > sma50).astype(int) - (c < sma50).astype(int)
        + (c > sma100).astype(int) - (c < sma100).astype(int)
        + (sma50 > sma50.shift(10)).astype(int) - (sma50 < sma50.shift(10)).astype(int)
        + (sma50 > sma100).astype(int) - (sma50 < sma100).astype(int)
    )
    if macd is not None:
        s = s + (macd > 0).astype(int) - (macd < 0).astype(int)
    mom = c / c.shift(21) - 1
    s = s + (mom > 0.03).astype(int) - (mom < -0.03).astype(int)

    raw = pd.Series(pd.NA, index=d.index, dtype="Float64")
    raw[s >= 2] = 1.0
    raw[s <= -2] = 0.0
    pos = raw.ffill().fillna(0.0).astype(float)

    ret = c.pct_change().fillna(0.0)
    strat_ret = pos.shift(1).fillna(0.0) * ret
    valid = sma100.notna()
    strat_ret, ret = strat_ret[valid], ret[valid]
    if len(strat_ret) < 60:
        return None

    strat_equity = (1 + strat_ret).cumprod()
    bh_equity = (1 + ret).cumprod()

    fwd_ret = (c.shift(-fwd) / c - 1)[valid]
    long_mask = (pos[valid] == 1) & fwd_ret.notna()
    hit_rate = float((fwd_ret[long_mask] > 0).mean()) if long_mask.any() else None
    exposure = float((pos[valid] == 1).mean())

    return {
        "strategy_return": float(strat_equity.iloc[-1] - 1),
        "buyhold_return": float(bh_equity.iloc[-1] - 1),
        "hit_rate": hit_rate,
        "fwd_days": fwd,
        "n_long_days": int(long_mask.sum()),
        "exposure": exposure,
        "equity": pd.DataFrame({"אסטרטגיה": strat_equity, "קנייה והחזקה": bh_equity}),
    }


# ----------------------------------------------------------------------------
# בניית הגרף — Plotly (אינטראקטיבי, תומך עברית + מצב לילה)
# ----------------------------------------------------------------------------
_CHART_TXT = {
    "he": {"close": "מחיר סגירה", "sma": "ממוצע {n}", "bb": "רצועות בולינגר",
           "vol": "מחזור", "title": "{sym} — מחיר ואינדיקטורים"},
    "en": {"close": "Close", "sma": "SMA {n}", "bb": "Bollinger (20,2)",
           "vol": "Volume", "title": "{sym} — Price & Indicators"},
}


def build_chart(df: pd.DataFrame, symbol: str, dark: bool = False, lang: str = "he",
                chart_type: str = "line"):
    d = df.tail(400)
    t = _CHART_TXT["en" if lang == "en" else "he"]

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
        row_heights=[0.5, 0.13, 0.18, 0.19],
        subplot_titles=(t["title"].format(sym=symbol), t["vol"], "RSI (14)", "MACD (12,26,9)"),
    )

    if chart_type == "candle" and {"Open", "High", "Low"}.issubset(d.columns):
        fig.add_trace(go.Candlestick(
            x=d.index, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"],
            name=t["close"], increasing_line_color="#2ca02c", decreasing_line_color="#d62728",
            showlegend=False,
        ), row=1, col=1)
        fig.update_xaxes(rangeslider_visible=False)
    else:
        fig.add_trace(go.Scatter(x=d.index, y=d["Close"], name=t["close"],
                                 line=dict(color="#1f77b4", width=1.7)), row=1, col=1)
    for n, col, color in ((50, "SMA50", "#ff7f0e"), (100, "SMA100", "#2ca02c"),
                          (200, "SMA200", "#d62728")):
        if d[col].notna().any():
            fig.add_trace(go.Scatter(x=d.index, y=d[col], name=t["sma"].format(n=n),
                                     line=dict(color=color, width=1.1)), row=1, col=1)
    if d["BB_high"].notna().any():
        fig.add_trace(go.Scatter(x=d.index, y=d["BB_high"], name=t["bb"],
                                 line=dict(color="#9467bd", width=0.6),
                                 showlegend=False, hoverinfo="skip"), row=1, col=1)
        fig.add_trace(go.Scatter(x=d.index, y=d["BB_low"], name=t["bb"],
                                 line=dict(color="#9467bd", width=0.6),
                                 fill="tonexty", fillcolor="rgba(148,103,189,0.13)",
                                 hoverinfo="skip"), row=1, col=1)

    fig.add_trace(go.Bar(x=d.index, y=d["Volume"], name=t["vol"],
                         marker_color="#8c8c8c", showlegend=False), row=2, col=1)

    fig.add_trace(go.Scatter(x=d.index, y=d["RSI"], name="RSI",
                             line=dict(color="#8c564b", width=1.4), showlegend=False),
                  row=3, col=1)
    fig.add_hline(y=70, line=dict(color="#d62728", dash="dash", width=0.8), row=3, col=1)
    fig.add_hline(y=30, line=dict(color="#2ca02c", dash="dash", width=0.8), row=3, col=1)
    fig.update_yaxes(range=[0, 100], row=3, col=1)

    fig.add_trace(go.Scatter(x=d.index, y=d["MACD"], name="MACD",
                             line=dict(color="#1f77b4", width=1.4), showlegend=False),
                  row=4, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["MACD_signal"], name="Signal",
                             line=dict(color="#ff7f0e", width=1.4), showlegend=False),
                  row=4, col=1)
    hist = d["MACD_hist"].fillna(0)
    fig.add_trace(go.Bar(x=d.index, y=hist, name="Histogram", showlegend=False,
                         marker_color=["#2ca02c" if v >= 0 else "#d62728" for v in hist]),
                  row=4, col=1)

    fig.update_layout(
        template="plotly_dark" if dark else "plotly_white",
        height=830, bargap=0,
        margin=dict(l=40, r=20, t=55, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0),
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ----------------------------------------------------------------------------
# השוואה בין מניות
# ----------------------------------------------------------------------------
def _compare_row(name: str, info: dict, hist: pd.DataFrame, price: float) -> dict:
    g = info.get
    chg = None
    if hist is not None and not hist.empty and len(hist) > 1:
        c0 = float(hist["Close"].iloc[0])
        chg = (price / c0 - 1) * 100 if c0 else None
    pe, _ = pe_ratio(info, g("currentPrice") or price)
    dr, dy = g("dividendRate"), g("dividendYield")
    dyf = (dr / price) if (dr and price) else (
        (dy / 100 if dy and abs(dy) > 1 else dy) if dy is not None else None)
    return {
        "סימול": name,
        "מחיר": fmt(price),
        "שינוי בטווח": f"{chg:+.1f}%" if chg is not None else "—",
        "שווי שוק": human_number(g("marketCap")),
        "P/E": fmt(pe) if pe else "—",
        "P/S": fmt(g("priceToSalesTrailing12Months")),
        "שולי רווח": fmt(g("profitMargins"), pct=True) if g("profitMargins") is not None else "—",
        "ROE": fmt(g("returnOnEquity"), pct=True) if g("returnOnEquity") is not None else "—",
        "צמיחת הכנסות": fmt(g("revenueGrowth"), pct=True) if g("revenueGrowth") is not None else "—",
        "תשואת דיבידנד": fmt(dyf, pct=True) if dyf is not None else "—",
        "בטא": fmt(g("beta")),
    }


def render_compare(base_symbol: str, base_df: pd.DataFrame, period: str,
                   others: list, dark: bool) -> None:
    st.subheader("⚖️ השוואה")
    st.caption("גרף מחיר מנורמל ל-100 בתחילת התקופה + טבלת מדדים. עד 4 מניות להשוואה.")

    series = {base_symbol: base_df["Close"]}
    rows = [_compare_row(base_symbol, {}, base_df, float(base_df["Close"].iloc[-1]))]
    # שורת הבסיס — נשתמש ב-info אמיתי דרך load_data המטמון
    try:
        b_hist, b_info, *_ = load_data(base_symbol, period)
        rows[0] = _compare_row(base_symbol, b_info or {}, b_hist, float(b_hist["Close"].iloc[-1]))
    except Exception:
        pass

    misses = []
    for sym in others:
        if sym == base_symbol:
            continue
        try:
            h, info_o, err, used, _resolved, _src = load_data(sym, period)
        except Exception:
            h, info_o, used = None, {}, sym
        if h is None or h.empty:
            misses.append(sym)
            continue
        series[used] = h["Close"]
        rows.append(_compare_row(used, info_o or {}, h, float(h["Close"].iloc[-1])))

    if misses:
        st.warning("לא נמצאו נתונים עבור: " + ", ".join(misses))

    # גרף מנורמל
    norm = pd.DataFrame(series).dropna(how="all")
    if not norm.empty:
        norm = norm / norm.bfill().iloc[0] * 100
        fig = go.Figure()
        for col in norm.columns:
            fig.add_trace(go.Scatter(x=norm.index, y=norm[col], name=str(col), mode="lines"))
        fig.update_layout(
            template="plotly_dark" if dark else "plotly_white",
            height=440, margin=dict(l=40, r=20, t=30, b=30),
            hovermode="x unified", yaxis_title="מנורמל ל-100",
            legend=dict(orientation="h", y=1.05),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### טבלת השוואה")
    st.table(pd.DataFrame(rows).set_index("סימול"))
    st.caption("מקור: Yahoo Finance. תאי '—' = הנתון לא זמין למניה זו (נפוץ במניות לא-אמריקאיות).")


# ----------------------------------------------------------------------------
# ממשק המשתמש
# ----------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="מנתח מניות", page_icon="📈", layout="wide")

    with st.sidebar:
        st.markdown("### ⚙️ הגדרות תצוגה")
        dark = st.toggle("🌙 מצב לילה", key="dark_mode")
        chart_style = st.radio(
            "סוג גרף מחיר", ["קו", "נרות יפניים"], horizontal=True, key="chart_style"
        )
        eng_chart = st.toggle(
            "תוויות גרף באנגלית", key="eng_chart",
            help="כברירת מחדל תוויות הגרף בעברית. הדלקה מציגה Close / SMA / Volume וכו'.",
        )
        translate_on = st.toggle(
            "🌐 תרגם טקסטים מאנגלית לעברית", key="translate_on",
            help="מתרגם סקטור, תעשייה ותיאור החברה. שירות חינמי — לעיתים איטי או לא זמין.",
        )
        st.markdown("---")
        compare_raw = st.text_input(
            "⚖️ השוואה מול (עד 4 סימולים, מופרדים בפסיק)", key="compare_syms",
            placeholder="MSFT, GOOGL, NVDA",
        )

        st.markdown("---")
        st.markdown("### ⚡ מעקב ובחירה מהירה")
        _QUICK = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META", "BTC-USD"]
        wl = st.session_state.setdefault("watchlist", [])
        recent = st.session_state.get("recent", [])
        pick_opts = ["—"] + list(dict.fromkeys(wl + recent + _QUICK))

        def _on_quickpick():
            v = st.session_state.get("quickpick")
            if v and v != "—":
                st.session_state["run"] = True
                st.session_state["symbol"] = v
                st.session_state.setdefault("period", "2y")

        st.selectbox("בחר סימול לניתוח מיידי", pick_opts, key="quickpick",
                     on_change=_on_quickpick)

        new_wl = st.multiselect(
            "⭐ רשימת מעקב", options=list(dict.fromkeys(wl + recent + _QUICK)), default=wl,
            help="הרשימה פרטית לך ונשמרת כל עוד הכרטיסייה פתוחה.",
        )
        if set(new_wl) != set(wl):
            st.session_state["watchlist"] = clean_watchlist(new_wl)
            st.rerun()

        st.caption(
            "למצב לילה מלא של המערכת: תפריט ☰ בפינה הימנית העליונה → "
            "Settings → Theme → Dark."
        )

    st.markdown(_page_css(dark), unsafe_allow_html=True)
    chart_lang = "en" if eng_chart else "he"
    chart_type = "candle" if chart_style == "נרות יפניים" else "line"
    compare_syms = [s.strip().upper() for s in (compare_raw or "").replace(";", ",").split(",")
                    if s.strip()][:4]

    st.title("📈 מנתח מניות — ניתוח טכני ופיננסי")
    st.caption(
        "כל הנתונים מגיעים מ-Yahoo Finance דרך הספרייה החינמית yfinance. "
        "אין צורך במפתח API ואין שום שירות בתשלום."
    )

    with st.form("analyze_form"):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            symbol_input = st.text_input(
                "סימול / שם חברה / קריפטו", value="AAPL",
                placeholder="מניה: AAPL, NVIDIA · בורסות עולם: TEVA.TA, SAP.DE · קריפטו: BTC, ETH-USD",
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
        st.session_state["symbol"] = (symbol_input or "").strip()
        st.session_state["period"] = period

    if st.session_state.get("run"):
        rc1, rc2 = st.columns([1, 1])
        if rc1.button("↺ ניתוח מניה חדשה (איפוס)", use_container_width=True):
            for _k in ("run", "symbol", "period"):
                st.session_state.pop(_k, None)
            st.rerun()
        _cur = (st.session_state.get("symbol") or "").strip().upper()
        _in_wl = _cur in st.session_state.get("watchlist", [])
        if _cur and rc2.button(
            ("★ במעקב — הסר" if _in_wl else "☆ הוסף לרשימת המעקב"),
            use_container_width=True, key="wl_toggle",
        ):
            _wl = st.session_state.setdefault("watchlist", [])
            _wl.remove(_cur) if _in_wl else _wl.append(_cur)
            st.session_state["watchlist"] = clean_watchlist(_wl)
            st.rerun()

    if not st.session_state.get("run"):
        st.info(
            "הזן סימול מניה, שם חברה, או מטבע קריפטו (למשל `BTC`, `ETH-USD`) "
            "למעלה ולחץ על **נתח מניה**."
        )
        st.stop()

    symbol = st.session_state["symbol"]
    period = st.session_state["period"]

    if not symbol:
        st.warning("יש להזין סימול מניה.")
        st.stop()

    with st.spinner(f"טוען נתונים עבור {symbol}…"):
        hist, info, load_err, used_symbol, resolved_name, price_source = load_data(symbol, period)

    if hist is None or hist.empty:
        st.error(
            f"לא הצלחתי לשלוף נתונים עבור '{symbol}'.\n\n"
            "בדוק שהזנת **סימול** תקין (למשל `NVDA` ולא `NVIDIA`, `META` ולא `Facebook`), "
            "או נסה להקליד את שם החברה במלואו. ייתכן גם ש-Yahoo חוסם זמנית — "
            "המתן דקה ולחץ שוב על 'נתח מניה'."
        )
        if load_err:
            st.caption(f"פרטי שגיאה: {load_err}")
        st.stop()

    symbol = used_symbol
    _rec = st.session_state.get("recent", [])
    st.session_state["recent"] = ([symbol] + [x for x in _rec if x != symbol])[:8]
    if resolved_name:
        st.success(f"לא נמצא הסימול שהוזן — מוצג במקומו **{used_symbol}** ({resolved_name}).")
    if price_source and price_source != "Yahoo Finance":
        st.warning(
            f"נתוני Yahoo לא היו זמינים — נתוני המחיר נשלפו מ**{price_source}**. "
            "ייתכן שחלק מהנתונים הפיננסיים חסרים."
        )

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
    reco = buy_recommendation(df, info, pe)

    company_name = info.get("longName") or info.get("shortName") or symbol
    currency = info.get("currency", "")
    sector = maybe_he(info.get("sector"), translate_on)
    industry = maybe_he(info.get("industry"), translate_on)
    crypto = is_crypto(info, symbol)

    # --- שורת מדדים עליונה (2 עמודות — קריא גם בטלפון) ---
    m1, m2 = st.columns(2)
    m3, m4 = st.columns(2)
    m1.metric(f"{symbol} — מחיר אחרון", price_str(price, currency))
    m2.metric("שינוי יומי", f"{day_change:+,.2f}", f"{day_change_pct:+.2f}%")
    m3.metric(f"שינוי בטווח ({period})", f"{period_change_pct:+.2f}%")
    if crypto:
        m4.metric("שווי שוק", human_number(info.get("marketCap")))
    else:
        m4.metric("מכפיל רווח (P/E)", fmt(pe) if pe else "—")

    if len(df) < 200:
        st.info(
            "טווח הנתונים קצר מ-200 ימי מסחר, לכן ממוצע נע 200 עשוי להיות חסר או חלקי. "
            "מומלץ לבחור טווח של שנתיים ומעלה."
        )

    tab_labels = ["🧭 סקירה כללית", "🧠 כדאיות קנייה", "💰 נתונים פיננסיים",
                  "📊 ניתוח טכני", "📈 גרפים", "🗂 נתונים גולמיים"]
    if compare_syms:
        tab_labels.insert(5, "⚖️ השוואה")
        tab_overview, tab_reco, tab_fund, tab_tech, tab_chart, tab_cmp, tab_raw = st.tabs(tab_labels)
    else:
        tab_cmp = None
        tab_overview, tab_reco, tab_fund, tab_tech, tab_chart, tab_raw = st.tabs(tab_labels)

    # --- סקירה כללית ---
    with tab_overview:
        st.subheader(company_name)
        meta = " · ".join(p for p in [sector, industry, info.get("exchange")] if p)
        if meta:
            st.write(meta)

        getattr(st, kind)(f"{icon}  סיכום טכני אוטומטי: **{verdict}**  (ניקוד: {score:+d})")
        getattr(st, reco["kind"])(
            f"🧠  שווה לקנות? **{reco['answer']}**"
            + (f"  ·  {reco['horizon_txt']}" if reco["positives"] else "")
        )

        cal = get_calendar_info(symbol)
        cal_bits = []
        if cal.get("earnings_date"):
            cal_bits.append(f"📅 דוח קרוב: **{cal['earnings_date']}**")
        if cal.get("ex_div"):
            cal_bits.append(f"💰 אקס-דיבידנד: {cal['ex_div']}")
        if cal_bits:
            st.markdown("  ·  ".join(cal_bits))

        news = get_news(symbol)
        if news:
            with st.expander(f"📰 חדשות אחרונות ({len(news)})"):
                for n in news:
                    ttl = maybe_he(n["title"], translate_on)
                    head = f"**[{ttl}]({n['link']})**" if n["link"] else f"**{ttl}**"
                    meta = " · ".join(x for x in [n["publisher"], n["when"]] if x)
                    st.markdown(head + (f"  \n{meta}" if meta else ""))

        summary = info.get("longBusinessSummary")
        if summary:
            with st.expander("תיאור החברה"):
                st.write(maybe_he(summary, translate_on))
                if not translate_on:
                    st.caption("להצגה בעברית: הדלק 'תרגם טקסטים' בסרגל הצד.")

    # --- כדאיות קנייה לפי טווח ---
    with tab_reco:
        getattr(st, reco["kind"])(f"🧠  שווה לקנות?  **{reco['answer']}**")
        if reco["positives"]:
            st.markdown(f"**טווח מומלץ לפי הניתוח:** {reco['horizon_txt']}")
        st.caption(
            "הפסק נקבע אוטומטית מתוך שקלול האיתותים בכל טווח: כל טווח שמקבל ניקוד ‎+2‎ "
            "ומעלה נחשב 'חיובי'. אם לפחות טווח אחד חיובי — התשובה 'כן', עם ציון הטווחים."
        )
        if crypto:
            st.caption(
                "עבור קריפטו הניקוד מבוסס על אינדיקטורים טכניים בלבד (אין נתוני יסוד "
                "כמו P/E). קריפטו תנודתי מאוד — יש להתייחס לתוצאה בזהירות רבה."
            )

        cols = st.columns(3)
        for col, (name, h) in zip(cols, reco["horizons"].items()):
            with col:
                st.markdown(f"### {h['dot']} טווח {name}")
                st.caption(h["range"])
                st.markdown(f"**{h['label']} {h['arrow']}**  ·  ניקוד {h['score']:+d}")
                for text, arrow in h["reasons"]:
                    st.markdown(f"- {arrow} {text}")
                if not h["reasons"]:
                    st.markdown("- אין מספיק נתונים")

        # --- בדיקה היסטורית (בקטסט) של האיתות ---
        with st.expander("📉 בדיקה היסטורית של האיתות (בקטסט)"):
            bt = backtest_signal(df)
            if bt is None:
                st.caption("אין מספיק היסטוריה לבקטסט — בחר טווח נתונים ארוך יותר (2y ומעלה).")
            else:
                b1, b2 = st.columns(2)
                b3, b4 = st.columns(2)
                b1.metric("תשואת האסטרטגיה", f"{bt['strategy_return'] * 100:+.1f}%")
                b2.metric("קנייה והחזקה", f"{bt['buyhold_return'] * 100:+.1f}%")
                b3.metric(
                    f"אחוז הצלחה ({bt['fwd_days']} ימים קדימה)",
                    f"{bt['hit_rate'] * 100:.0f}%" if bt["hit_rate"] is not None else "—",
                )
                b4.metric("חשיפה לשוק", f"{bt['exposure'] * 100:.0f}%")
                eq = bt["equity"]
                bfig = go.Figure()
                for col in eq.columns:
                    bfig.add_trace(go.Scatter(x=eq.index, y=eq[col], name=col, mode="lines"))
                bfig.update_layout(
                    template="plotly_dark" if dark else "plotly_white",
                    height=300, margin=dict(l=40, r=20, t=20, b=25),
                    hovermode="x unified", legend=dict(orientation="h", y=1.1),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(bfig, use_container_width=True)
                st.caption(
                    "האסטרטגיה: לונג כשניקוד המגמה ‎+2‎ ומעלה, מחוץ לשוק כשהוא ‎−2‎ ומטה. "
                    "לא כולל עמלות/מיסים, לא כולל שורט, ומבוסס על גרסה מפושטת של הניקוד. "
                    "ביצועי עבר אינם מבטיחים דבר."
                )

        st.warning(
            "⚠️ זהו סיכום טכני אוטומטי בלבד ואינו ייעוץ השקעות, המלצה אישית או הבטחה לתשואה. "
            "אינדיקטורים מתארים את העבר וההווה ואינם חוזים את העתיד. החלטות השקעה הן באחריותך."
        )

    # --- נתונים פיננסיים ---
    with tab_fund:
        if crypto:
            st.subheader(f"נתוני מטבע — {company_name}")
            st.info(
                "מדובר במטבע קריפטו. נתוני יסוד של חברה (מכפיל רווח, דוחות כספיים, "
                "תחזיות אנליסטים, SEC) אינם רלוונטיים; מוצגים נתוני היצע, שווי שוק ונפח מסחר."
            )
            for title, rows in crypto_sections(info, price).items():
                vals = [str(v) for v in rows.values()]
                with st.expander(title, expanded=True):
                    st.table(pd.DataFrame({"פרמטר": list(rows), "ערך": vals}).set_index("פרמטר"))
            st.caption(
                f"מקורות: נתוני מחיר ומטבע — {price_source or 'Yahoo Finance'} "
                "(CoinMarketCap דרך yfinance). ניתוח טכני מלא זמין בכרטיסייה 'ניתוח טכני'."
            )
        else:
            st.subheader("נתונים פיננסיים")

            c1, c2 = st.columns(2)
            c3, c4 = st.columns(2)
            c1.metric("מכפיל רווח (P/E)", fmt(pe) if pe else "—")
            c2.metric("שווי שוק", human_number(info.get("marketCap")))
            c3.metric("רווח למניה (EPS)", fmt(info.get("trailingEps")))
            _tgt = info.get("targetMeanPrice")
            c4.metric("מחיר יעד ממוצע", price_str(_tgt, currency) if _tgt else "—",
                      f"{(_tgt / price - 1) * 100:+.1f}%" if (_tgt and price) else None)

            st.markdown(
                f"**{company_name}** · {sector or '—'} · {industry or '—'} · "
                f"{info.get('exchange', '—')} · {currency or '—'}"
            )

            sections = financial_sections(info, price)
            for title, rows in sections.items():
                vals = [str(v) for v in rows.values()]
                if all(v in ("—", "nan", "None", "") for v in vals):
                    continue
                with st.expander(title, expanded=title.startswith("הערכת שווי")):
                    st.table(pd.DataFrame({"פרמטר": list(rows), "ערך": vals}).set_index("פרמטר"))

            if not info or len(info) < 5:
                st.warning(
                    "Yahoo Finance החזיר מידע חברה חלקי או ריק. נסה שוב בעוד דקה, "
                    "או ראה את מקור SEC EDGAR למטה (למניות ארה\"ב)."
                )

            # --- מקור עצמאי #2: SEC EDGAR ---
            st.markdown("### 🏛️ מקור עצמאי: SEC EDGAR (דוחות רשמיים)")
            sec_df, sec_note = get_sec_facts(symbol)
            if sec_df is not None and not sec_df.empty:
                show = sec_df.map(lambda v: human_number(v) if isinstance(v, (int, float)) else v)
                st.table(show)
            st.caption(sec_note)

            # --- דוחות כספיים מלאים (yfinance) ---
            st.markdown("### 📑 דוחות כספיים מלאים")
            statements = get_statements(symbol)
            if statements:
                for label, sdf in statements.items():
                    with st.expander(label):
                        show = sdf.map(
                            lambda v: human_number(v)
                            if isinstance(v, (int, float)) and pd.notna(v) else v
                        )
                        st.dataframe(show, use_container_width=True)
            else:
                st.caption("לא התקבלו דוחות כספיים עבור סימול זה.")

            st.caption(
                f"מקורות: נתוני מחיר — {price_source or 'Yahoo Finance'} · "
                "מכפילים ותחזיות — Yahoo Finance · דוחות רשמיים — SEC EDGAR (data.sec.gov). "
                "ערכים ממקורות שונים עשויים להיות מעודכנים לתאריכים שונים."
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
        for label, key, dg in (
            ("סטוכסטי %K", "STOCH_K", 1), ("סטוכסטי %D", "STOCH_D", 1),
            ("ADX (14) — עוצמת מגמה", "ADX", 1),
            ("ATR (14)", "ATR", 2), ("ATR כאחוז מהמחיר", "ATR_pct", 2),
            ("OBV — מאזן נפח", "OBV", 0),
        ):
            if key in latest and is_num(latest.get(key)):
                tech_vals[label] = (human_number(latest[key]) if key == "OBV"
                                    else fmt(latest[key], digits=dg))
        tech_df = pd.DataFrame(
            {"אינדיקטור": list(tech_vals.keys()), "ערך": list(tech_vals.values())}
        )
        st.dataframe(tech_df, hide_index=True, use_container_width=True)

        st.markdown("#### פירוט האיתותים")
        st.dataframe(signals_df, hide_index=True, use_container_width=True)

    # --- גרפים ---
    with tab_chart:
        fig = build_chart(df, symbol, dark=dark, lang=chart_lang, chart_type=chart_type)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "גרף אינטראקטיבי — אפשר להצביע לראות ערכים, לגרור לזום ולהקליק על מקרא. "
            "מוצגים עד 400 ימי המסחר האחרונים. סוג הגרף (קו / נרות) נשלט בסרגל הצד."
        )

    # --- השוואה מול מניות אחרות ---
    if tab_cmp is not None:
        with tab_cmp:
            render_compare(symbol, df, period, compare_syms, dark)

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
