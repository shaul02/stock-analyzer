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

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import ADXIndicator, MACD, SMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import OnBalanceVolumeIndicator

# עיצוב בסיסי. הכיוון (rtl/ltr) נקבע לפי שפת הממשק.
# חשוב: לא לגעת ב-.stApp / stAppViewContainer עצמם — RTL עליהם שובר את
# אנימציית פתיחה/סגירה של סרגל הצד. מחילים כיוון רק על תוכן הראשי ותוכן הסיידבר.
def _base_css(rtl: bool) -> str:
    d = "rtl" if rtl else "ltr"
    align = "right" if rtl else "left"
    return f"""
      [data-testid="stMain"], section.main, .main {{ direction: {d}; }}
      [data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3,
      [data-testid="stMain"] h4, [data-testid="stMain"] p, [data-testid="stMain"] label,
      [data-testid="stMain"] .stMarkdown {{ text-align: {align}; }}
      [data-testid="stMetric"] {{ direction: ltr; text-align: left; }}
      [data-testid="stTable"], [data-testid="stDataFrame"] {{ direction: ltr; }}
      [data-testid="stSidebarUserContent"] {{ direction: {d}; text-align: {align}; }}
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


def _page_css(dark: bool, rtl: bool = True) -> str:
    return f"<style>{_base_css(rtl)}{_DARK_CSS if dark else ''}</style>"


# ----------------------------------------------------------------------------
# רב-לשוני (עברית / אנגלית / רוסית). עברית = ברירת מחדל.
# ----------------------------------------------------------------------------
LANGS = {"he": "עברית", "en": "English", "ru": "Русский"}


def get_lang() -> str:
    return st.session_state.get("lang", "he")


def is_rtl() -> bool:
    return get_lang() == "he"


def t(key: str, **kw) -> str:
    d = STRINGS.get(key, {})
    s = d.get(get_lang()) or d.get("he") or key
    return s.format(**kw) if kw else s


try:
    from translations import DEEP as _DEEP
except Exception:  # pragma: no cover
    _DEEP = {}


def L(he: str, **kw) -> str:
    """תרגום עומק לפי מחרוזת המקור העברית. חסר / שפה=he -> מחזיר את המקור."""
    if not he:
        return he
    lang = get_lang()
    s = he if lang == "he" else _DEEP.get(he, {}).get(lang, he)
    return s.format(**kw) if kw else s


STRINGS: dict[str, dict[str, str]] = {
    # --- כותרת ראשית ---
    "app_title": {
        "he": "📈 מנתח מניות — ניתוח טכני ופיננסי",
        "en": "📈 Stock Analyzer — Technical & Fundamental",
        "ru": "📈 Анализатор акций — теханализ и фундамент",
    },
    "app_caption": {
        "he": "כל הנתונים מגיעים מ-Yahoo Finance דרך הספרייה החינמית yfinance. "
              "אין צורך במפתח API ואין שום שירות בתשלום.",
        "en": "All data comes from Yahoo Finance via the free yfinance library. "
              "No API key, no paid services.",
        "ru": "Все данные — из Yahoo Finance через бесплатную библиотеку yfinance. "
              "Без API-ключа и платных сервисов.",
    },
    # --- סרגל הצד ---
    "sb_display": {"he": "⚙️ הגדרות תצוגה", "en": "⚙️ Display settings", "ru": "⚙️ Настройки отображения"},
    "sb_language": {"he": "🌐 שפה", "en": "🌐 Language", "ru": "🌐 Язык"},
    "sb_dark": {"he": "🌙 מצב לילה", "en": "🌙 Dark mode", "ru": "🌙 Тёмная тема"},
    "sb_chart_type": {"he": "סוג גרף מחיר", "en": "Price chart type", "ru": "Тип графика цены"},
    "sb_line": {"he": "קו", "en": "Line", "ru": "Линия"},
    "sb_candle": {"he": "נרות יפניים", "en": "Candlesticks", "ru": "Свечи"},
    "sb_compact": {
        "he": "📱 גרף קומפקטי (לטלפון)", "en": "📱 Compact chart (mobile)",
        "ru": "📱 Компактный график (моб.)",
    },
    "sb_compact_help": {
        "he": "גרפים נמוכים יותר, פחות היסטוריה — נוח לצפייה בטלפון.",
        "en": "Shorter charts, less history — easier to view on a phone.",
        "ru": "Более низкие графики, меньше истории — удобно на телефоне.",
    },
    "sb_overlays": {
        "he": "📐 תמיכה/התנגדות + קווי מגמה אוטומטיים",
        "en": "📐 Auto support/resistance + trendlines",
        "ru": "📐 Авто уровни поддержки/сопротивления + тренды",
    },
    "sb_overlays_help": {
        "he": "מזהה רמות מחיר חוזרות וקווי מגמה ומצייר אותם על גרף המחיר. "
              "אפשר גם לצייר קווים משלך בעזרת סרגל הכלים של הגרף.",
        "en": "Detects repeated price levels and trendlines and draws them on the price chart. "
              "You can also draw your own lines with the chart toolbar.",
        "ru": "Находит повторяющиеся ценовые уровни и линии тренда и рисует их. "
              "Свои линии можно чертить через панель инструментов графика.",
    },
    "sb_translate": {
        "he": "🌐 תרגם טקסטים מ-Yahoo לשפת הממשק",
        "en": "🌐 Translate Yahoo texts to UI language",
        "ru": "🌐 Переводить тексты Yahoo на язык интерфейса",
    },
    "sb_translate_help": {
        "he": "מתרגם סקטור, תעשייה ותיאור החברה. שירות חינמי — לעיתים איטי או לא זמין.",
        "en": "Translates sector, industry and company description. Free service — sometimes slow.",
        "ru": "Переводит сектор, отрасль и описание компании. Бесплатный сервис — бывает медленным.",
    },
    "sb_compare": {
        "he": "⚖️ השוואה מול (עד 4 סימולים, מופרדים בפסיק)",
        "en": "⚖️ Compare with (up to 4 symbols, comma-separated)",
        "ru": "⚖️ Сравнить с (до 4 тикеров через запятую)",
    },
    "sb_quick_head": {
        "he": "⚡ מעקב ובחירה מהירה", "en": "⚡ Watchlist & quick pick",
        "ru": "⚡ Список наблюдения и быстрый выбор",
    },
    "sb_quick_pick": {
        "he": "בחר סימול לניתוח מיידי", "en": "Pick a symbol to analyze now",
        "ru": "Выберите тикер для анализа",
    },
    "sb_watchlist": {"he": "⭐ רשימת מעקב", "en": "⭐ Watchlist", "ru": "⭐ Список наблюдения"},
    "sb_watchlist_help": {
        "he": "הרשימה פרטית לך ונשמרת כל עוד הכרטיסייה פתוחה.",
        "en": "Private to you, kept while this tab stays open.",
        "ru": "Личный список, хранится пока открыта вкладка.",
    },
    "sb_dark_hint": {
        "he": "למצב לילה מלא של המערכת: תפריט ☰ בפינה → Settings → Theme → Dark.",
        "en": "Full system dark mode: ☰ menu → Settings → Theme → Dark.",
        "ru": "Полная тёмная тема: меню ☰ → Settings → Theme → Dark.",
    },
    # --- טופס ---
    "f_symbol": {
        "he": "סימול / שם חברה / קריפטו", "en": "Symbol / company name / crypto",
        "ru": "Тикер / название компании / крипто",
    },
    "f_symbol_ph": {
        "he": "מניה: AAPL, NVIDIA · בורסות עולם: TEVA.TA, SAP.DE · קריפטו: BTC, ETH-USD",
        "en": "Stock: AAPL, NVIDIA · World: TEVA.TA, SAP.DE · Crypto: BTC, ETH-USD",
        "ru": "Акция: AAPL, NVIDIA · Мир: TEVA.TA, SAP.DE · Крипто: BTC, ETH-USD",
    },
    "f_period": {"he": "טווח נתונים", "en": "Data range", "ru": "Период данных"},
    "f_analyze": {"he": "🔍 נתח מניה", "en": "🔍 Analyze", "ru": "🔍 Анализировать"},
    "b_reset": {
        "he": "↺ ניתוח מניה חדשה (איפוס)", "en": "↺ New analysis (reset)",
        "ru": "↺ Новый анализ (сброс)",
    },
    "b_wl_add": {"he": "☆ הוסף לרשימת המעקב", "en": "☆ Add to watchlist", "ru": "☆ В список наблюдения"},
    "b_wl_remove": {"he": "★ במעקב — הסר", "en": "★ In watchlist — remove", "ru": "★ В списке — убрать"},
    # --- הודעות ---
    "msg_enter": {
        "he": "הזן סימול מניה, שם חברה, או מטבע קריפטו (למשל BTC, ETH-USD) למעלה ולחץ על נתח מניה.",
        "en": "Enter a symbol, company name or crypto (e.g. BTC, ETH-USD) above and click Analyze.",
        "ru": "Введите тикер, название компании или крипто (напр. BTC, ETH-USD) и нажмите «Анализировать».",
    },
    "msg_need_symbol": {"he": "יש להזין סימול מניה.", "en": "Please enter a symbol.",
                        "ru": "Введите тикер."},
    "msg_load_fail": {
        "he": "לא הצלחתי לשלוף נתונים עבור '{sym}'.\n\nבדוק שהזנת סימול תקין "
              "(למשל NVDA ולא NVIDIA), או נסה שם חברה מלא. ייתכן גם ש-Yahoo חוסם זמנית — "
              "המתן דקה ונסה שוב.",
        "en": "Couldn't fetch data for '{sym}'.\n\nCheck the symbol (e.g. NVDA not NVIDIA), "
              "or try the full company name. Yahoo may be rate-limiting — wait a minute and retry.",
        "ru": "Не удалось получить данные для «{sym}».\n\nПроверьте тикер (напр. NVDA, не NVIDIA) "
              "или введите полное название. Возможен временный лимит Yahoo — подождите минуту.",
    },
    "msg_err_detail": {"he": "פרטי שגיאה: {err}", "en": "Error detail: {err}",
                       "ru": "Детали ошибки: {err}"},
    "msg_resolved": {
        "he": "לא נמצא הסימול שהוזן — מוצג במקומו {sym} ({name}).",
        "en": "Entered symbol not found — showing {sym} ({name}) instead.",
        "ru": "Тикер не найден — показан {sym} ({name}).",
    },
    "msg_stooq": {
        "he": "נתוני Yahoo לא היו זמינים — נתוני המחיר נשלפו מ-{src}. חלק מהנתונים הפיננסיים עשויים לחסור.",
        "en": "Yahoo data unavailable — prices fetched from {src}. Some fundamentals may be missing.",
        "ru": "Данные Yahoo недоступны — цены получены из {src}. Часть фундаментала может отсутствовать.",
    },
    "msg_short_range": {
        "he": "טווח הנתונים קצר מ-200 ימי מסחר, לכן ממוצע נע 200 עשוי להיות חסר. מומלץ טווח של שנתיים ומעלה.",
        "en": "Data range is under 200 trading days, so the 200-day MA may be missing. Prefer 2y or more.",
        "ru": "Диапазон меньше 200 торговых дней — MA(200) может отсутствовать. Лучше 2 года и больше.",
    },
    # --- שורת מדדים ---
    "m_last_price": {"he": "{sym} — מחיר אחרון", "en": "{sym} — last price", "ru": "{sym} — последняя цена"},
    "m_day_change": {"he": "שינוי יומי", "en": "Daily change", "ru": "Изменение за день"},
    "m_period_change": {"he": "שינוי בטווח ({p})", "en": "Change over ({p})", "ru": "Изменение за ({p})"},
    "m_pe": {"he": "מכפיל רווח (P/E)", "en": "P/E ratio", "ru": "P/E"},
    "m_mcap": {"he": "שווי שוק", "en": "Market cap", "ru": "Капитализация"},
    "m_eps": {"he": "רווח למניה (EPS)", "en": "EPS", "ru": "EPS"},
    "m_target": {"he": "מחיר יעד ממוצע", "en": "Avg. price target", "ru": "Средний таргет"},
    # --- כרטיסיות ---
    "tab_overview": {"he": "🧭 סקירה כללית", "en": "🧭 Overview", "ru": "🧭 Обзор"},
    "tab_reco": {"he": "🧠 כדאיות קנייה", "en": "🧠 Buy signal", "ru": "🧠 Стоит ли покупать"},
    "tab_fund": {"he": "💰 נתונים פיננסיים", "en": "💰 Financials", "ru": "💰 Финансы"},
    "tab_tech": {"he": "📊 ניתוח טכני", "en": "📊 Technicals", "ru": "📊 Теханализ"},
    "tab_chart": {"he": "📈 גרפים", "en": "📈 Charts", "ru": "📈 Графики"},
    "tab_cmp": {"he": "⚖️ השוואה", "en": "⚖️ Compare", "ru": "⚖️ Сравнение"},
    "tab_raw": {"he": "🗂 נתונים גולמיים", "en": "🗂 Raw data", "ru": "🗂 Сырые данные"},
    # --- פסקי דין ---
    "v_bullish": {"he": "מגמה חיובית (Bullish)", "en": "Bullish trend", "ru": "Бычий тренд (Bullish)"},
    "v_bearish": {"he": "מגמה שלילית (Bearish)", "en": "Bearish trend", "ru": "Медвежий тренд (Bearish)"},
    "v_neutral": {"he": "ניטרלי (Neutral)", "en": "Neutral", "ru": "Нейтрально"},
    "tech_summary_line": {
        "he": "{icon}  סיכום טכני אוטומטי: **{v}**  (ניקוד: {s})",
        "en": "{icon}  Automatic technical summary: **{v}**  (score: {s})",
        "ru": "{icon}  Автоматический теханализ: **{v}**  (счёт: {s})",
    },
    "reco_yes": {"he": "כן — האיתותים תומכים בקנייה", "en": "Yes — signals support buying",
                 "ru": "Да — сигналы за покупку"},
    "reco_no": {"he": "לא כרגע — האיתותים הטכניים שליליים", "en": "Not now — technical signals are negative",
                "ru": "Не сейчас — сигналы отрицательные"},
    "reco_unclear": {"he": "לא חד-משמעי — עדיף להמתין לאיתות ברור",
                     "en": "Unclear — better wait for a clear signal",
                     "ru": "Неоднозначно — лучше дождаться чёткого сигнала"},
    "reco_line": {
        "he": "🧠  שווה לקנות? **{ans}**", "en": "🧠  Worth buying? **{ans}**",
        "ru": "🧠  Стоит покупать? **{ans}**",
    },
    "reco_horizon": {
        "he": "**טווח מומלץ לפי הניתוח:** {txt}", "en": "**Recommended horizon:** {txt}",
        "ru": "**Рекомендуемый горизонт:** {txt}",
    },
    "reco_horizon_suffix": {"he": "טווח {names}", "en": "{names} term", "ru": "{names} срок"},
    "hz_short": {"he": "קצר", "en": "short", "ru": "краткий"},
    "hz_medium": {"he": "בינוני", "en": "medium", "ru": "средний"},
    "hz_long": {"he": "ארוך", "en": "long", "ru": "долгий"},
    # --- אזהרות ---
    "disc_reco": {
        "he": "⚠️ זהו סיכום טכני אוטומטי בלבד ואינו ייעוץ השקעות, המלצה אישית או הבטחה לתשואה. "
              "אינדיקטורים מתארים עבר והווה ואינם חוזים עתיד. החלטות השקעה באחריותך.",
        "en": "⚠️ Automated technical summary only — not investment advice, a personal recommendation "
              "or a promise of returns. Indicators describe past and present, not the future. "
              "Investment decisions are your own.",
        "ru": "⚠️ Только автоматический теханализ — не инвестиционный совет и не гарантия доходности. "
              "Индикаторы описывают прошлое и настоящее, а не будущее. Решения — на вашей ответственности.",
    },
    "disc_footer": {
        "he": "⚠️ הכלי מיועד ללימוד ולמחקר בלבד ואינו מהווה ייעוץ השקעות. "
              "נתוני Yahoo Finance עשויים להיות מושהים או לא מדויקים.",
        "en": "⚠️ For learning and research only — not investment advice. "
              "Yahoo Finance data may be delayed or inaccurate.",
        "ru": "⚠️ Только для обучения и исследований — не инвестиционный совет. "
              "Данные Yahoo Finance могут быть с задержкой или неточными.",
    },
    # --- גרפים ---
    "chart_caption": {
        "he": "גרף אינטראקטיבי — הצבע לערכים, גרור לזום, השתמש בסרגל הכלים כדי לצייר קווים משלך. "
              "מוצגים עד {n} ימי מסחר. סוג הגרף (קו/נרות) וקווים אוטומטיים — בסרגל הצד.",
        "en": "Interactive chart — hover for values, drag to zoom, use the toolbar to draw your own lines. "
              "Up to {n} trading days shown. Chart type and auto lines are in the sidebar.",
        "ru": "Интерактивный график — наведите для значений, тяните для зума, рисуйте свои линии панелью. "
              "Показано до {n} торговых дней. Тип графика и авто-линии — в боковой панели.",
    },
    "sr_support": {"he": "קו תמיכה", "en": "Support line", "ru": "Линия поддержки"},
    "sr_resistance": {"he": "קו התנגדות", "en": "Resistance line", "ru": "Линия сопротивления"},
    # --- בקטסט ---
    "bt_title": {"he": "📉 בדיקה היסטורית של האיתות (בקטסט)", "en": "📉 Signal backtest",
                 "ru": "📉 Историческая проверка сигнала (бэктест)"},
    "bt_strat": {"he": "תשואת האסטרטגיה", "en": "Strategy return", "ru": "Доходность стратегии"},
    "bt_bh": {"he": "קנייה והחזקה", "en": "Buy & hold", "ru": "Купить и держать"},
    "bt_hit": {"he": "אחוז הצלחה ({d} ימים קדימה)", "en": "Hit rate ({d}d forward)",
               "ru": "Доля успеха ({d} дн. вперёд)"},
    "bt_exposure": {"he": "חשיפה לשוק", "en": "Market exposure", "ru": "Экспозиция на рынок"},
    "bt_none": {
        "he": "אין מספיק היסטוריה לבקטסט — בחר טווח נתונים ארוך יותר (2y ומעלה).",
        "en": "Not enough history for a backtest — pick a longer range (2y+).",
        "ru": "Недостаточно истории для бэктеста — выберите период подлиннее (2 года+).",
    },
    "bt_caption": {
        "he": "האסטרטגיה: לונג כשניקוד המגמה +2 ומעלה, מחוץ לשוק כשהוא -2 ומטה. "
              "ללא עמלות/מיסים, ללא שורט, גרסה מפושטת של הניקוד. ביצועי עבר אינם מבטיחים דבר.",
        "en": "Strategy: long when the trend score is +2 or more, flat when -2 or less. "
              "No fees/taxes, no shorting, simplified score. Past performance guarantees nothing.",
        "ru": "Стратегия: лонг при счёте тренда +2 и выше, вне рынка при -2 и ниже. "
              "Без комиссий/налогов, без шортов, упрощённый счёт. Прошлые результаты ничего не гарантируют.",
    },
    # --- סטטוס טווח ---
    "st_pos": {"he": "חיובי", "en": "Positive", "ru": "Положительно"},
    "st_neg": {"he": "שלילי", "en": "Negative", "ru": "Отрицательно"},
    "st_neu": {"he": "ניטרלי", "en": "Neutral", "ru": "Нейтрально"},
    "hz_head": {"he": "טווח {name}", "en": "{name} term", "ru": "{name} срок"},
    "reco_score": {"he": "**{st} {arrow}**  ·  ניקוד {s}", "en": "**{st} {arrow}**  ·  score {s}",
                   "ru": "**{st} {arrow}**  ·  счёт {s}"},
    "reco_caption": {
        "he": "הפסק נקבע מתוך שקלול האיתותים בכל טווח: טווח בניקוד +2 ומעלה נחשב 'חיובי'. "
              "אם לפחות טווח אחד חיובי — התשובה 'כן', עם ציון הטווחים.",
        "en": "The verdict weighs each horizon's signals: a horizon scoring +2 or more is 'positive'. "
              "If at least one horizon is positive the answer is 'yes', naming the horizons.",
        "ru": "Вердикт взвешивает сигналы по каждому горизонту: счёт +2 и выше — «положительно». "
              "Если хотя бы один горизонт положителен — ответ «да» с указанием горизонтов.",
    },
    "reco_crypto_caption": {
        "he": "עבור קריפטו הניקוד מבוסס על אינדיקטורים טכניים בלבד (אין P/E). "
              "קריפטו תנודתי מאוד — יש להתייחס לתוצאה בזהירות רבה.",
        "en": "For crypto the score is technical-only (no P/E). Crypto is very volatile — "
              "treat the result with extra caution.",
        "ru": "Для крипто счёт только технический (без P/E). Крипто очень волатильно — "
              "относитесь к результату с особой осторожностью.",
    },
    "reco_no_data": {"he": "- אין מספיק נתונים", "en": "- not enough data", "ru": "- недостаточно данных"},
    # --- סקירה ---
    "ov_earnings": {"he": "📅 דוח קרוב: **{d}**", "en": "📅 Next earnings: **{d}**",
                    "ru": "📅 Ближайший отчёт: **{d}**"},
    "ov_exdiv": {"he": "💰 אקס-דיבידנד: {d}", "en": "💰 Ex-dividend: {d}", "ru": "💰 Экс-дивиденд: {d}"},
    "ov_news": {"he": "📰 חדשות אחרונות ({n})", "en": "📰 Recent news ({n})",
                "ru": "📰 Последние новости ({n})"},
    "ov_company": {"he": "תיאור החברה", "en": "Company description", "ru": "Описание компании"},
    "ov_translate_hint": {
        "he": "להצגה בשפת הממשק: הדלק 'תרגם טקסטים' בסרגל הצד.",
        "en": "To show in the UI language: enable 'Translate texts' in the sidebar.",
        "ru": "Показать на языке интерфейса: включите «Переводить тексты» в боковой панели.",
    },
    # --- השוואה ---
    "cmp_title": {"he": "⚖️ השוואה", "en": "⚖️ Compare", "ru": "⚖️ Сравнение"},
    "cmp_caption": {
        "he": "גרף מחיר מנורמל ל-100 בתחילת התקופה + טבלת מדדים. עד 4 מניות.",
        "en": "Price chart rebased to 100 at the start + a metrics table. Up to 4 stocks.",
        "ru": "График цены, приведённый к 100 в начале + таблица метрик. До 4 акций.",
    },
    "cmp_miss": {"he": "לא נמצאו נתונים עבור: {syms}", "en": "No data for: {syms}",
                 "ru": "Нет данных для: {syms}"},
    "cmp_table": {"he": "#### טבלת השוואה", "en": "#### Comparison table", "ru": "#### Таблица сравнения"},
    "cmp_source": {
        "he": "מקור: Yahoo Finance. תאי '—' = הנתון לא זמין (נפוץ במניות לא-אמריקאיות).",
        "en": "Source: Yahoo Finance. '—' = value unavailable (common for non-US stocks).",
        "ru": "Источник: Yahoo Finance. «—» = значение недоступно (часто для не-США акций).",
    },
    "cmp_norm": {"he": "מנורמל ל-100", "en": "Rebased to 100", "ru": "Приведено к 100"},
    "cr_symbol": {"he": "סימול", "en": "Symbol", "ru": "Тикер"},
    "cr_price": {"he": "מחיר", "en": "Price", "ru": "Цена"},
    "cr_change": {"he": "שינוי בטווח", "en": "Change (period)", "ru": "Изменение за период"},
    "cr_mcap": {"he": "שווי שוק", "en": "Market cap", "ru": "Капитализация"},
    "cr_margin": {"he": "שולי רווח", "en": "Profit margin", "ru": "Маржа прибыли"},
    "cr_rev_growth": {"he": "צמיחת הכנסות", "en": "Revenue growth", "ru": "Рост выручки"},
    "cr_div_yield": {"he": "תשואת דיבידנד", "en": "Dividend yield", "ru": "Див. доходность"},
    "cr_beta": {"he": "בטא", "en": "Beta", "ru": "Бета"},
    "bt_eq_strat": {"he": "אסטרטגיה", "en": "Strategy", "ru": "Стратегия"},
    "bt_eq_bh": {"he": "קנייה והחזקה", "en": "Buy & hold", "ru": "Купить и держать"},
    # --- כללי ---
    "raw_download": {"he": "⬇ הורדת כל הנתונים כקובץ CSV", "en": "⬇ Download all data as CSV",
                     "ru": "⬇ Скачать все данные в CSV"},
    "tech_caption": {
        "he": "הניקוד מסכם את האיתותים בטבלה למטה: כל איתות חיובי מוסיף נקודה, כל שלילי מוריד. "
              "+2 ומעלה = Bullish, -2 ומטה = Bearish, ביניהם = Neutral.",
        "en": "The score sums the signals below: each positive adds a point, each negative subtracts. "
              "+2 or more = Bullish, -2 or less = Bearish, in between = Neutral.",
        "ru": "Счёт суммирует сигналы ниже: плюс добавляет очко, минус отнимает. "
              "+2 и выше = Bullish, -2 и ниже = Bearish, между — Neutral.",
    },
    "tech_values_head": {"he": "#### ערכי האינדיקטורים האחרונים", "en": "#### Latest indicator values",
                         "ru": "#### Последние значения индикаторов"},
    "tech_signals_head": {"he": "#### פירוט האיתותים", "en": "#### Signal breakdown",
                          "ru": "#### Разбор сигналов"},
    "i18n_partial": {
        "he": "", "en": "ℹ️ Detailed labels in this table are being translated — some rows still show Hebrew.",
        "ru": "ℹ️ Подробные подписи в этой таблице ещё переводятся — часть строк пока на иврите.",
    },
}


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
# תרגום אופציונלי של טקסטים מ-Yahoo (שירות חינמי, ללא מפתח). נכשל בשקט.
# ----------------------------------------------------------------------------
_GT_TARGET = {"he": "iw", "en": "en", "ru": "ru"}


@st.cache_data(ttl=86400, show_spinner=False)
def translate_text(text: str, target: str = "iw") -> str:
    text = (text or "").strip()
    if not text:
        return ""
    try:
        from deep_translator import GoogleTranslator

        out = GoogleTranslator(source="auto", target=target).translate(text[:4800])
        if not out:
            return text
        low = out.lower()
        if any(b in low for b in ("that’s an error", "that's an error", "error 500",
                                  "<html", "server error")):
            return text  # השירות החינמי החזיר דף שגיאה — נשארים עם המקור
        return out
    except Exception:
        return text


def translate_he(text: str) -> str:  # תאימות לאחור (בדיקות/קריאות ישנות)
    return translate_text(text, "iw")


def maybe_he(text, enabled: bool):
    """מתרגם לשפת הממשק רק אם המתג דלוק ויש טקסט."""
    if not (enabled and text):
        return text
    return translate_text(str(text), _GT_TARGET.get(get_lang(), "en"))


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
        L("הערכת שווי (Valuation)"): {
            L("שווי שוק"): money("marketCap"),
            L("שווי מיזם (EV)"): money("enterpriseValue"),
            L("מכפיל רווח נגרר (P/E)"): num("trailingPE"),
            L("מכפיל רווח עתידי (Fwd P/E)"): num("forwardPE"),
            L("מכפיל PEG"): num("trailingPegRatio") if g("trailingPegRatio") else num("pegRatio"),
            L("מחיר / מכירות (P/S)"): num("priceToSalesTrailing12Months"),
            L("מחיר / הון עצמי (P/B)"): num("priceToBook"),
            "EV / EBITDA": num("enterpriseToEbitda"),
            L("EV / הכנסות"): num("enterpriseToRevenue"),
            L("מחיר / תזרים חופשי (P/FCF)"): p_fcf,
        },
        L("רווחיות (Profitability)"): {
            L("שולי רווח גולמי"): pct("grossMargins"),
            L("שולי רווח תפעולי"): pct("operatingMargins"),
            L("שולי רווח נקי"): pct("profitMargins"),
            L("שולי EBITDA"): pct("ebitdaMargins"),
            L("תשואה על ההון (ROE)"): pct("returnOnEquity"),
            L("תשואה על הנכסים (ROA)"): pct("returnOnAssets"),
        },
        L("צמיחה (Growth)"): {
            L("צמיחת הכנסות (שנתי)"): pct("revenueGrowth"),
            L("צמיחת רווח (שנתי)"): pct("earningsGrowth"),
            L("צמיחת רווח רבעוני (YoY)"): pct("earningsQuarterlyGrowth"),
            L("הכנסות 12 חודשים"): money("totalRevenue"),
            L("רווח נקי (12 ח')"): money("netIncomeToCommon"),
            "EBITDA": money("ebitda"),
        },
        L("איתנות פיננסית (Balance Sheet)"): {
            L("מזומן ושווי מזומן"): money("totalCash"),
            L("חוב כולל"): money("totalDebt"),
            L("חוב נטו"): human_number((g("totalDebt") or 0) - (g("totalCash") or 0))
            if (g("totalDebt") or g("totalCash")) else "—",
            L("יחס חוב להון (D/E)"): num("debtToEquity"),
            L("יחס שוטף (Current)"): num("currentRatio"),
            L("יחס מהיר (Quick)"): num("quickRatio"),
            L("מזומן למניה"): num("totalCashPerShare"),
            L("תזרים חופשי (FCF)"): money("freeCashflow"),
            L("תזרים תפעולי"): money("operatingCashflow"),
        },
        L("דיבידנד"): {
            L("דיבידנד למניה (שנתי)"): num("dividendRate"),
            L("תשואת דיבידנד"): fmt(div_yield_frac, pct=True) if div_yield_frac is not None else "—",
            L("תשואה ממוצעת 5 שנים"): fmt(div_5y, pct=True) if div_5y is not None else "—",
            L("יחס חלוקה (Payout)"): pct("payoutRatio"),
        },
        L("תחזית אנליסטים"): {
            L("המלצה"): str(g("recommendationKey") or "—").upper(),
            L("מספר אנליסטים"): num("numberOfAnalystOpinions", digits=0),
            L("מחיר יעד ממוצע"): num("targetMeanPrice"),
            L("מחיר יעד גבוה"): num("targetHighPrice"),
            L("מחיר יעד נמוך"): num("targetLowPrice"),
            L("פוטנציאל מול מחיר נוכחי"):
                fmt((g("targetMeanPrice") / price - 1), pct=True)
                if (g("targetMeanPrice") and price) else "—",
        },
        L("מניה ומסחר"): {
            L("מניות במחזור"): money("sharesOutstanding"),
            L("מניות חופשיות (Float)"): money("floatShares"),
            L("אחזקת מוסדיים"): pct("heldPercentInstitutions"),
            L("פוזיציות שורט (% מ-Float)"): pct("shortPercentOfFloat"),
            L("בטא (Beta)"): num("beta"),
            L("טווח 52 שבועות"): f'{fmt(g("fiftyTwoWeekLow"))} – {fmt(g("fiftyTwoWeekHigh"))}',
            L("מחזור מסחר ממוצע"): money("averageVolume"),
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
        L("נתוני מטבע"): {
            L("שווי שוק"): human_number(g("marketCap")),
            L("היצע במחזור"): human_number(supply),
            L("היצע מרבי / כולל"): human_number(max_supply),
            L("אחוז מההיצע המרבי"):
                fmt(supply / max_supply, pct=True) if (supply and max_supply) else "—",
            L("נפח מסחר 24 שעות"):
                human_number(g("volume24Hr") or g("regularMarketVolume") or g("volume")),
            L("מטבע התייחסות"): g("currency") or "USD",
            L("אלגוריתם"): g("algorithm") or "—",
            L("טווח 52 שבועות"):
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
    """מחזיר (DataFrame שנתי לפי שנה, (תבנית-הערה, ערך)). DataFrame ריק אם לא רלוונטי/נכשל.

    ההערה מוחזרת כ-(מחרוזת עברית עם {x} אם צריך, ערך להצבה) כדי לאפשר תרגום ב-main.
    """
    cik = _sec_ticker_map().get((symbol or "").upper())
    if not cik:
        return pd.DataFrame(), (
            'לא נמצאה חברה אמריקאית תואמת ב-SEC EDGAR (רלוונטי למניות בארה"ב).', None)
    try:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        req = urllib.request.Request(url, headers=_SEC_UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            facts = json.loads(resp.read().decode("utf-8")).get("facts", {}).get("us-gaap", {})
    except Exception as err:  # noqa: BLE001
        return pd.DataFrame(), ("קריאת SEC EDGAR נכשלה: {x}", err)

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
        return pd.DataFrame(), ("SEC EDGAR: לא נמצאו נתוני דוח שנתי במבנה צפוי.", None)

    years = sorted(rows)[-6:]
    table = pd.DataFrame(
        {str(y): rows[y] for y in years},
        index=[lbl for lbl, _, _ in _SEC_CONCEPTS],
    )
    return table, ("מקור: SEC EDGAR · CIK {x} · דוחות 10-K/20-F רשמיים.", cik)


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

    C_IND, C_SIG, C_TXT = L("אינדיקטור"), L("איתות"), L("פירוש")

    def add(ok, label, bull, bear, neutral=None):
        nonlocal score
        label = L(label)
        if ok is None:
            rows.append({C_IND: label, C_SIG: "—", C_TXT: L("אין מספיק נתונים")})
        elif ok:
            score += 1
            rows.append({C_IND: label, C_SIG: L("חיובי ▲"), C_TXT: L(bull)})
        elif ok is False:
            score -= 1
            rows.append({C_IND: label, C_SIG: L("שלילי ▼"), C_TXT: L(bear)})
        else:  # "neutral"
            rows.append({C_IND: label, C_SIG: L("ניטרלי ◆"), C_TXT: L(neutral)})

    def row(ind, sig, txt):
        rows.append({C_IND: ind, C_SIG: sig, C_TXT: txt})

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
        _ri = L("RSI (14) = {x}", x=f"{rsi:.1f}")
        if rsi < 30:
            score += 1
            row(_ri, L("חיובי ▲"), L("מכירת יתר — פוטנציאל לתיקון כלפי מעלה"))
        elif rsi > 70:
            score -= 1
            row(_ri, L("שלילי ▼"), L("קניית יתר — סיכון לתיקון כלפי מטה"))
        else:
            row(_ri, L("ניטרלי ◆"), L("בטווח מאוזן (30–70)"))
    else:
        row(L("RSI (14)"), "—", L("אין מספיק נתונים"))

    add(macd > macd_sig if (is_num(macd) and is_num(macd_sig)) else None,
        "MACD מול קו הסיגנל",
        "MACD מעל קו הסיגנל — מומנטום חיובי",
        "MACD מתחת לקו הסיגנל — מומנטום שלילי")

    _bb = L("רצועות בולינגר")
    if is_num(bb_high) and is_num(bb_low):
        if price > bb_high:
            score -= 1
            row(_bb, L("שלילי ▼"), L("המחיר מעל הרצועה העליונה — מתיחות/קניית יתר"))
        elif price < bb_low:
            score += 1
            row(_bb, L("חיובי ▲"), L("המחיר מתחת לרצועה התחתונה — מתיחות/מכירת יתר"))
        else:
            row(_bb, L("ניטרלי ◆"), L("המחיר בתוך הרצועות"))
    else:
        row(_bb, "—", L("אין מספיק נתונים"))

    stoch_k = latest.get("STOCH_K")
    if is_num(stoch_k):
        _sk = L("סטוכסטי %K = {x}", x=f"{stoch_k:.0f}")
        if stoch_k < 20:
            score += 1
            row(_sk, L("חיובי ▲"), L("מכירת יתר (מתחת ל-20)"))
        elif stoch_k > 80:
            score -= 1
            row(_sk, L("שלילי ▼"), L("קניית יתר (מעל 80)"))
        else:
            row(_sk, L("ניטרלי ◆"), L("בטווח מאוזן (20–80)"))

    adx = latest.get("ADX")
    if is_num(adx):
        strength = L("מגמה חזקה") if adx >= 25 else (
            L("מגמה חלשה/דשדוש") if adx < 20 else L("מגמה מתגבשת"))
        row(L("ADX (14) = {x}", x=f"{adx:.0f}"), L("מידע"),
            L("{x} — ADX מודד עוצמת מגמה, לא כיוון", x=strength))

    atr_pct = latest.get("ATR_pct")
    if is_num(atr_pct):
        row(L("ATR = {x}% מהמחיר", x=f"{atr_pct:.1f}"), L("מידע"),
            L("תנודתיות יומית ממוצעת — שימושי לתמחור סטופ-לוס"))

    if score >= 2:
        verdict, icon, kind = "v_bullish", "🟢", "success"
    elif score <= -2:
        verdict, icon, kind = "v_bearish", "🔴", "error"
    else:
        verdict, icon, kind = "v_neutral", "🟡", "info"

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
    """מחזיר (status יציב, חץ, נקודה). status: pos / neg / neu."""
    if score >= 2:
        return "pos", "▲", "🟢"
    if score <= -2:
        return "neg", "▼", "🔴"
    return "neu", "◆", "🟡"


def _horizon_short(df: pd.DataFrame):
    """טווח קצר (ימים עד שבועות ספורים) — מומנטום ותנודתיות."""
    latest = df.iloc[-1]
    price = float(latest["Close"])
    reasons, score = [], 0

    bb_mid = latest.get("BB_mid")  # ממוצע 20 יום
    if is_num(bb_mid):
        if price > bb_mid:
            score += 1
            reasons.append((L("המחיר מעל ממוצע 20 יום"), "▲"))
        else:
            score -= 1
            reasons.append((L("המחיר מתחת לממוצע 20 יום"), "▼"))

    hist = df["MACD_hist"].dropna()
    if len(hist) >= 2:
        if hist.iloc[-1] > 0 and hist.iloc[-1] >= hist.iloc[-2]:
            score += 1
            reasons.append((L("מומנטום MACD חיובי ומתחזק"), "▲"))
        elif hist.iloc[-1] < 0 and hist.iloc[-1] <= hist.iloc[-2]:
            score -= 1
            reasons.append((L("מומנטום MACD שלילי ומתחזק כלפי מטה"), "▼"))
        else:
            reasons.append((L("מומנטום MACD מעורב"), "◆"))

    rsi = latest.get("RSI")
    if is_num(rsi):
        _r = f"{rsi:.0f}"
        if rsi < 30:
            score += 1
            reasons.append((L("RSI = {x} — מכירת יתר, אפשרות לתיקון מעלה", x=_r), "▲"))
        elif rsi > 70:
            score -= 1
            reasons.append((L("RSI = {x} — קניית יתר, סיכון לתיקון מטה", x=_r), "▼"))
        elif rsi >= 50:
            score += 1
            reasons.append((L("RSI = {x} — חיובי בלי קיצון", x=_r), "▲"))
        else:
            reasons.append((L("RSI = {x} — חלש", x=_r), "◆"))

    chg5 = _series_change(df["Close"], 5)
    if chg5 is not None:
        if chg5 > 2:
            score += 1
            reasons.append((L("עלייה של {x}% ב-5 ימי מסחר אחרונים", x=f"{chg5:+.1f}"), "▲"))
        elif chg5 < -2:
            score -= 1
            reasons.append((L("ירידה של {x}% ב-5 ימי מסחר אחרונים", x=f"{chg5:+.1f}"), "▼"))

    bb_high, bb_low = latest.get("BB_high"), latest.get("BB_low")
    if is_num(bb_high) and is_num(bb_low) and bb_high > bb_low:
        pctb = (price - bb_low) / (bb_high - bb_low)
        if pctb < 0.2:
            score += 1
            reasons.append((L("המחיר קרוב לרצועת בולינגר התחתונה"), "▲"))
        elif pctb > 0.9:
            score -= 1
            reasons.append((L("המחיר קרוב לרצועת בולינגר העליונה"), "▼"))

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
                reasons.append((L("המחיר מעל ממוצע {x} יום", x=win), "▲"))
            else:
                score -= 1
                reasons.append((L("המחיר מתחת לממוצע {x} יום", x=win), "▼"))

    sl = _slope(df["SMA50"], 10)
    if sl is not None:
        if sl > 0:
            score += 1
            reasons.append((L("ממוצע 50 יום במגמת עלייה"), "▲"))
        else:
            score -= 1
            reasons.append((L("ממוצע 50 יום במגמת ירידה"), "▼"))

    sma50, sma100 = latest.get("SMA50"), latest.get("SMA100")
    if is_num(sma50) and is_num(sma100):
        if sma50 > sma100:
            score += 1
            reasons.append((L("ממוצע 50 מעל ממוצע 100"), "▲"))
        else:
            score -= 1
            reasons.append((L("ממוצע 50 מתחת לממוצע 100"), "▼"))

    macd = latest.get("MACD")
    if is_num(macd):
        if macd > 0:
            score += 1
            reasons.append((L("MACD מעל קו האפס"), "▲"))
        else:
            score -= 1
            reasons.append((L("MACD מתחת לקו האפס"), "▼"))

    chg21 = _series_change(df["Close"], 21)
    if chg21 is not None:
        if chg21 > 3:
            score += 1
            reasons.append((L("עלייה של {x}% בחודש האחרון", x=f"{chg21:+.1f}"), "▲"))
        elif chg21 < -3:
            score -= 1
            reasons.append((L("ירידה של {x}% בחודש האחרון", x=f"{chg21:+.1f}"), "▼"))

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
            reasons.append((L("המחיר מעל ממוצע 200 יום"), "▲"))
        else:
            score -= 1
            reasons.append((L("המחיר מתחת לממוצע 200 יום"), "▼"))
        if price > sma200 * 1.4:
            score -= 1
            reasons.append((L("המחיר מתוח מאוד מעל ממוצע 200 יום (סיכון תיקון)"), "▼"))

    sma50 = latest.get("SMA50")
    if is_num(sma50) and is_num(sma200):
        if sma50 > sma200:
            score += 1
            reasons.append((L("'צלב זהב' — ממוצע 50 מעל ממוצע 200"), "▲"))
        else:
            score -= 1
            reasons.append((L("'צלב מוות' — ממוצע 50 מתחת לממוצע 200"), "▼"))

    sl = _slope(df["SMA200"], 21)
    if sl is not None:
        if sl > 0:
            score += 1
            reasons.append((L("ממוצע 200 יום במגמת עלייה"), "▲"))
        else:
            score -= 1
            reasons.append((L("ממוצע 200 יום במגמת ירידה"), "▼"))

    hi = info.get("fiftyTwoWeekHigh")
    lo = info.get("fiftyTwoWeekLow")
    if is_num(hi) and hi and price >= hi * 0.85:
        score += 1
        reasons.append((L("קרוב לשיא 52 שבועות — מגמה חזקה"), "▲"))
    elif is_num(lo) and lo and price <= lo * 1.1:
        score -= 1
        reasons.append((L("קרוב לשפל 52 שבועות — חולשה"), "▼"))

    if pe is not None:
        _p = f"{pe:.0f}"
        if pe <= 0:
            score -= 1
            reasons.append((L("החברה מפסידה (P/E שלילי)"), "▼"))
        elif pe <= 25:
            score += 1
            reasons.append((L("מכפיל רווח סביר (P/E ≈ {x})", x=_p), "▲"))
        elif pe <= 40:
            reasons.append((L("מכפיל רווח גבוה (P/E ≈ {x})", x=_p), "◆"))
        else:
            score -= 1
            reasons.append((L("מכפיל רווח גבוה מאוד (P/E ≈ {x})", x=_p), "▼"))

    peg = info.get("pegRatio")
    if is_num(peg):
        if 0 < peg < 1:
            score += 1
            reasons.append((L("PEG ≈ {x} — צמיחה אטרקטיבית מול המחיר", x=f"{peg:.2f}"), "▲"))
        elif peg > 2.5:
            score -= 1
            reasons.append((L("PEG ≈ {x} — יקר יחסית לצמיחה", x=f"{peg:.2f}"), "▼"))

    return score, reasons


# טווח id -> תיאור זמן (מפתח יציב; התיאור מתורגם בתצוגה, כרגע עברית)
HORIZON_META = {
    "short": {"he": "ימים עד שבועות ספורים", "en": "days to a few weeks",
              "ru": "дни — несколько недель"},
    "medium": {"he": "שבועות עד מספר חודשים", "en": "weeks to a few months",
               "ru": "недели — несколько месяцев"},
    "long": {"he": "מספר חודשים עד שנים", "en": "months to years",
             "ru": "месяцы — годы"},
}


def buy_recommendation(df: pd.DataFrame, info: dict, pe):
    """מחזיר dict עם פסק כללי + פירוט לכל טווח (מפתחות יציבים). לא ייעוץ."""
    horizons = {}
    for hid, (sc, reasons) in {
        "short": _horizon_short(df),
        "medium": _horizon_medium(df),
        "long": _horizon_long(df, info, pe),
    }.items():
        status, arrow, dot = _label(sc)
        horizons[hid] = {
            "status": status, "arrow": arrow, "dot": dot,
            "score": sc, "reasons": reasons,
        }

    positives = [h for h, v in horizons.items() if v["status"] == "pos"]
    negatives = [h for h, v in horizons.items() if v["status"] == "neg"]

    if positives:
        answer_key, kind = "reco_yes", "success"
    elif negatives and not positives:
        answer_key, kind = "reco_no", "error"
    else:
        answer_key, kind = "reco_unclear", "info"

    return {
        "answer_key": answer_key,
        "kind": kind,
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
        "equity": pd.DataFrame({"strategy": strat_equity, "buyhold": bh_equity}),
    }


# ----------------------------------------------------------------------------
# זיהוי אוטומטי של רמות תמיכה/התנגדות וקווי מגמה
# ----------------------------------------------------------------------------
def swing_points(close: pd.Series, window: int = 8):
    """אינדקסים (מספריים) של שיאים ושפלים מקומיים לאורך חלון מרכזי."""
    v = np.asarray(close, dtype=float)
    highs, lows = [], []
    for i in range(window, len(v) - window):
        seg = v[i - window: i + window + 1]
        if v[i] == seg.max():
            highs.append(i)
        elif v[i] == seg.min():
            lows.append(i)
    return highs, lows


def support_resistance(df: pd.DataFrame, window: int = 8, max_levels: int = 4,
                       tol: float = 0.012, lookback: int = 260):
    """רמות מחיר אופקיות שחזרו לפחות פעמיים (אשכולות של פיבוטים)."""
    close = df["Close"].tail(lookback).reset_index(drop=True)
    if len(close) < 3 * window:
        return []
    hi, lo = swing_points(close, window)
    prices = sorted(close.iloc[hi + lo].tolist())
    if not prices:
        return []
    clusters = [[prices[0]]]
    for p in prices[1:]:
        if p <= clusters[-1][-1] * (1 + tol):
            clusters[-1].append(p)
        else:
            clusters.append([p])
    levels = [(sum(c) / len(c), len(c)) for c in clusters if len(c) >= 2]
    levels.sort(key=lambda x: -x[1])
    return [round(lv, 4) for lv, _ in levels[:max_levels]]


def trendlines(df: pd.DataFrame, window: int = 8, lookback: int = 170):
    """קו מגמה עולה דרך השפלים וקו יורד דרך השיאים, על פני התקופה הנראית."""
    seg = df["Close"].tail(lookback)
    idx = seg.index
    y = seg.reset_index(drop=True)
    if len(y) < 3 * window:
        return {}
    hi, lo = swing_points(y, window)
    out = {}
    for key, pts in (("support", lo), ("resistance", hi)):
        if len(pts) >= 2:
            x = np.array(pts, dtype=float)
            m, b = np.polyfit(x, y.iloc[pts].to_numpy(dtype=float), 1)
            x0, x1 = 0, len(y) - 1
            out[key] = {"x": [idx[x0], idx[x1]], "y": [m * x0 + b, m * x1 + b]}
    return out


# ----------------------------------------------------------------------------
# בניית הגרף — Plotly (אינטראקטיבי, רב-לשוני, מצב לילה, ציור קווים)
# ----------------------------------------------------------------------------
_CHART_TXT = {
    "he": {"close": "מחיר סגירה", "sma": "ממוצע {n}", "bb": "רצועות בולינגר",
           "vol": "מחזור", "title": "{sym} — מחיר ואינדיקטורים",
           "support": "קו תמיכה", "resistance": "קו התנגדות"},
    "en": {"close": "Close", "sma": "SMA {n}", "bb": "Bollinger (20,2)",
           "vol": "Volume", "title": "{sym} — Price & Indicators",
           "support": "Support", "resistance": "Resistance"},
    "ru": {"close": "Цена закрытия", "sma": "SMA {n}", "bb": "Боллинджер (20,2)",
           "vol": "Объём", "title": "{sym} — цена и индикаторы",
           "support": "Поддержка", "resistance": "Сопротивление"},
}


def build_chart(df: pd.DataFrame, symbol: str, dark: bool = False, lang: str = "he",
                chart_type: str = "line", compact: bool = False, overlays: bool = False):
    d = df.tail(220 if compact else 400)
    t = _CHART_TXT.get(lang, _CHART_TXT["en"])

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05 if compact else 0.04,
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

    if overlays:
        lo_p, hi_p = float(d["Close"].min()), float(d["Close"].max())
        for lv in support_resistance(df):
            if lo_p * 0.9 <= lv <= hi_p * 1.1:
                fig.add_hline(y=lv, line=dict(color="#7f7f7f", dash="dot", width=1),
                              annotation_text=f"{lv:,.2f}", annotation_position="top left",
                              annotation_font_size=9, row=1, col=1)
        tl = trendlines(df)
        for key, seg, color in (("support", tl.get("support"), "#2ca02c"),
                                ("resistance", tl.get("resistance"), "#d62728")):
            if seg:
                fig.add_trace(go.Scatter(
                    x=seg["x"], y=seg["y"], mode="lines", name=t.get(key, key),
                    line=dict(color=color, dash="dash", width=1.6), hoverinfo="skip",
                ), row=1, col=1)

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
        height=560 if compact else 820, bargap=0,
        margin=dict(l=30, r=10, t=44, b=22) if compact else dict(l=40, r=20, t=55, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0,
                    font=dict(size=9 if compact else 12)),
        hovermode="x unified",
        font=dict(size=10 if compact else 12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_annotations(font_size=10 if compact else 13)  # כותרות תת-הגרפים
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
        t("cr_symbol"): name,
        t("cr_price"): fmt(price),
        t("cr_change"): f"{chg:+.1f}%" if chg is not None else "—",
        t("cr_mcap"): human_number(g("marketCap")),
        "P/E": fmt(pe) if pe else "—",
        "P/S": fmt(g("priceToSalesTrailing12Months")),
        t("cr_margin"): fmt(g("profitMargins"), pct=True) if g("profitMargins") is not None else "—",
        "ROE": fmt(g("returnOnEquity"), pct=True) if g("returnOnEquity") is not None else "—",
        t("cr_rev_growth"): fmt(g("revenueGrowth"), pct=True) if g("revenueGrowth") is not None else "—",
        t("cr_div_yield"): fmt(dyf, pct=True) if dyf is not None else "—",
        t("cr_beta"): fmt(g("beta")),
    }


def render_compare(base_symbol: str, base_df: pd.DataFrame, period: str,
                   others: list, dark: bool, compact: bool = False) -> None:
    st.subheader(t("cmp_title"))
    st.caption(t("cmp_caption"))

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
        st.warning(t("cmp_miss", syms=", ".join(misses)))

    # גרף מנורמל
    norm = pd.DataFrame(series).dropna(how="all")
    if not norm.empty:
        norm = norm / norm.bfill().iloc[0] * 100
        fig = go.Figure()
        for col in norm.columns:
            fig.add_trace(go.Scatter(x=norm.index, y=norm[col], name=str(col), mode="lines"))
        fig.update_layout(
            template="plotly_dark" if dark else "plotly_white",
            height=300 if compact else 440,
            margin=dict(l=30, r=10, t=24, b=22) if compact else dict(l=40, r=20, t=30, b=30),
            hovermode="x unified", yaxis_title=t("cmp_norm"),
            legend=dict(orientation="h", y=1.05, font=dict(size=9 if compact else 12)),
            font=dict(size=10 if compact else 12),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True, config={"responsive": True})

    st.markdown(t("cmp_table"))
    # טרנספוזיציה — מדדים בשורות, מניות בעמודות: נכנס יפה גם במסך טלפון
    st.table(pd.DataFrame(rows).set_index(t("cr_symbol")).T)
    st.caption(t("cmp_source"))


# ----------------------------------------------------------------------------
# ממשק המשתמש
# ----------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="מנתח מניות", page_icon="📈", layout="wide")

    with st.sidebar:
        st.radio(
            t("sb_language"), list(LANGS), format_func=lambda k: LANGS[k],
            horizontal=True, key="lang",
        )
        st.markdown(f"### {t('sb_display')}")
        dark = st.toggle(t("sb_dark"), key="dark_mode")
        chart_style = st.radio(
            t("sb_chart_type"), ["line", "candle"], horizontal=True, key="chart_style",
            format_func=lambda k: t("sb_line") if k == "line" else t("sb_candle"),
        )
        compact_chart = st.toggle(t("sb_compact"), key="compact_chart", help=t("sb_compact_help"))
        overlays_on = st.toggle(t("sb_overlays"), key="overlays_on", help=t("sb_overlays_help"))
        translate_on = st.toggle(t("sb_translate"), key="translate_on", help=t("sb_translate_help"))
        st.markdown("---")
        compare_raw = st.text_input(t("sb_compare"), key="compare_syms",
                                    placeholder="MSFT, GOOGL, NVDA")

        st.markdown("---")
        st.markdown(f"### {t('sb_quick_head')}")
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

        st.selectbox(t("sb_quick_pick"), pick_opts, key="quickpick", on_change=_on_quickpick)

        new_wl = st.multiselect(
            t("sb_watchlist"), options=list(dict.fromkeys(wl + recent + _QUICK)), default=wl,
            help=t("sb_watchlist_help"),
        )
        if set(new_wl) != set(wl):
            st.session_state["watchlist"] = clean_watchlist(new_wl)
            st.rerun()

        st.caption(t("sb_dark_hint"))

    st.markdown(_page_css(dark, rtl=is_rtl()), unsafe_allow_html=True)
    chart_lang = get_lang()
    chart_type = chart_style
    compare_syms = [s.strip().upper() for s in (compare_raw or "").replace(";", ",").split(",")
                    if s.strip()][:4]

    st.title(t("app_title"))
    st.caption(t("app_caption"))

    with st.form("analyze_form"):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            symbol_input = st.text_input(t("f_symbol"), value="AAPL", placeholder=t("f_symbol_ph"))
        with c2:
            period = st.selectbox(t("f_period"), ["6mo", "1y", "2y", "5y", "10y", "max"], index=2)
        with c3:
            st.markdown("<div style='height:1.9em'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button(t("f_analyze"), use_container_width=True)

    if submitted:
        st.session_state["run"] = True
        st.session_state["symbol"] = (symbol_input or "").strip()
        st.session_state["period"] = period

    if st.session_state.get("run"):
        rc1, rc2 = st.columns([1, 1])
        if rc1.button(t("b_reset"), use_container_width=True):
            for _k in ("run", "symbol", "period"):
                st.session_state.pop(_k, None)
            st.rerun()
        _cur = (st.session_state.get("symbol") or "").strip().upper()
        _in_wl = _cur in st.session_state.get("watchlist", [])
        if _cur and rc2.button(t("b_wl_remove") if _in_wl else t("b_wl_add"),
                               use_container_width=True, key="wl_toggle"):
            _wl = st.session_state.setdefault("watchlist", [])
            _wl.remove(_cur) if _in_wl else _wl.append(_cur)
            st.session_state["watchlist"] = clean_watchlist(_wl)
            st.rerun()

    if not st.session_state.get("run"):
        st.info(t("msg_enter"))
        st.stop()

    symbol = st.session_state["symbol"]
    period = st.session_state["period"]

    if not symbol:
        st.warning(t("msg_need_symbol"))
        st.stop()

    with st.spinner(f"{t('f_analyze')} — {symbol}…"):
        hist, info, load_err, used_symbol, resolved_name, price_source = load_data(symbol, period)

    if hist is None or hist.empty:
        st.error(t("msg_load_fail", sym=symbol))
        if load_err:
            st.caption(t("msg_err_detail", err=load_err))
        st.stop()

    symbol = used_symbol
    _rec = st.session_state.get("recent", [])
    st.session_state["recent"] = ([symbol] + [x for x in _rec if x != symbol])[:8]
    if resolved_name:
        st.success(t("msg_resolved", sym=used_symbol, name=resolved_name))
    if price_source and price_source != "Yahoo Finance":
        st.warning(t("msg_stooq", src=price_source))

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
    m1.metric(t("m_last_price", sym=symbol), price_str(price, currency))
    m2.metric(t("m_day_change"), f"{day_change:+,.2f}", f"{day_change_pct:+.2f}%")
    m3.metric(t("m_period_change", p=period), f"{period_change_pct:+.2f}%")
    if crypto:
        m4.metric(t("m_mcap"), human_number(info.get("marketCap")))
    else:
        m4.metric(t("m_pe"), fmt(pe) if pe else "—")

    if len(df) < 200:
        st.info(t("msg_short_range"))

    verdict_txt = t(verdict)
    horizon_names = " + ".join(t("hz_" + h) for h in reco["positives"])
    horizon_txt = t("reco_horizon_suffix", names=horizon_names) if reco["positives"] else "—"

    tab_labels = [t("tab_overview"), t("tab_reco"), t("tab_fund"),
                  t("tab_tech"), t("tab_chart"), t("tab_raw")]
    if compare_syms:
        tab_labels.insert(5, t("tab_cmp"))
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

        getattr(st, kind)(t("tech_summary_line", icon=icon, v=verdict_txt, s=f"{score:+d}"))
        getattr(st, reco["kind"])(
            t("reco_line", ans=t(reco["answer_key"]))
            + (f"  ·  {horizon_txt}" if reco["positives"] else "")
        )

        cal = get_calendar_info(symbol)
        cal_bits = []
        if cal.get("earnings_date"):
            cal_bits.append(t("ov_earnings", d=cal["earnings_date"]))
        if cal.get("ex_div"):
            cal_bits.append(t("ov_exdiv", d=cal["ex_div"]))
        if cal_bits:
            st.markdown("  ·  ".join(cal_bits))

        news = get_news(symbol)
        if news:
            with st.expander(t("ov_news", n=len(news))):
                for n in news:
                    ttl = maybe_he(n["title"], translate_on)
                    head = f"**[{ttl}]({n['link']})**" if n["link"] else f"**{ttl}**"
                    meta = " · ".join(x for x in [n["publisher"], n["when"]] if x)
                    st.markdown(head + (f"  \n{meta}" if meta else ""))

        summary = info.get("longBusinessSummary")
        if summary:
            with st.expander(t("ov_company")):
                st.write(maybe_he(summary, translate_on))
                if not translate_on and get_lang() != "en":
                    st.caption(t("ov_translate_hint"))

    # --- כדאיות קנייה לפי טווח ---
    with tab_reco:
        getattr(st, reco["kind"])(t("reco_line", ans=t(reco["answer_key"])))
        if reco["positives"]:
            st.markdown(t("reco_horizon", txt=horizon_txt))
        st.caption(t("reco_caption"))
        if crypto:
            st.caption(t("reco_crypto_caption"))

        cols = st.columns(3)
        for col, (hid, h) in zip(cols, reco["horizons"].items()):
            with col:
                st.markdown(f"### {h['dot']} " + t("hz_head", name=t("hz_" + hid)))
                st.caption(HORIZON_META[hid].get(get_lang(), HORIZON_META[hid]["he"]))
                st.markdown(t("reco_score", st=t("st_" + h["status"]), arrow=h["arrow"],
                              s=f"{h['score']:+d}"))
                for text, arrow in h["reasons"]:
                    st.markdown(f"- {arrow} {text}")
                if not h["reasons"]:
                    st.markdown(t("reco_no_data"))

        # --- בדיקה היסטורית (בקטסט) של האיתות ---
        with st.expander(t("bt_title")):
            bt = backtest_signal(df)
            if bt is None:
                st.caption(t("bt_none"))
            else:
                b1, b2 = st.columns(2)
                b3, b4 = st.columns(2)
                b1.metric(t("bt_strat"), f"{bt['strategy_return'] * 100:+.1f}%")
                b2.metric(t("bt_bh"), f"{bt['buyhold_return'] * 100:+.1f}%")
                b3.metric(
                    t("bt_hit", d=bt["fwd_days"]),
                    f"{bt['hit_rate'] * 100:.0f}%" if bt["hit_rate"] is not None else "—",
                )
                b4.metric(t("bt_exposure"), f"{bt['exposure'] * 100:.0f}%")
                eq = bt["equity"]
                bfig = go.Figure()
                _eqname = {"strategy": t("bt_eq_strat"), "buyhold": t("bt_eq_bh")}
                for col in eq.columns:
                    bfig.add_trace(go.Scatter(x=eq.index, y=eq[col],
                                              name=_eqname.get(col, col), mode="lines"))
                bfig.update_layout(
                    template="plotly_dark" if dark else "plotly_white",
                    height=210 if compact_chart else 300,
                    margin=dict(l=30, r=10, t=16, b=20) if compact_chart
                    else dict(l=40, r=20, t=20, b=25),
                    hovermode="x unified",
                    legend=dict(orientation="h", y=1.1, font=dict(size=9 if compact_chart else 12)),
                    font=dict(size=10 if compact_chart else 12),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(bfig, use_container_width=True, config={"responsive": True})
                st.caption(t("bt_caption"))

        st.warning(t("disc_reco"))

    # --- נתונים פיננסיים ---
    _PARAM, _VAL = L("פרמטר"), L("ערך")
    with tab_fund:
        if crypto:
            st.subheader(L("נתוני מטבע — {a}", a=company_name))
            st.info(L(
                "מדובר במטבע קריפטו. נתוני יסוד של חברה (מכפיל רווח, דוחות כספיים, "
                "תחזיות אנליסטים, SEC) אינם רלוונטיים; מוצגים נתוני היצע, שווי שוק ונפח מסחר."
            ))
            for title, rows in crypto_sections(info, price).items():
                vals = [str(v) for v in rows.values()]
                with st.expander(title, expanded=True):
                    st.table(pd.DataFrame({_PARAM: list(rows), _VAL: vals}).set_index(_PARAM))
            st.caption(L(
                "מקורות: נתוני מחיר ומטבע — {a} (CoinMarketCap דרך yfinance). "
                "ניתוח טכני מלא זמין בכרטיסייה 'ניתוח טכני'.", a=price_source or "Yahoo Finance"))
        else:
            st.subheader(L("נתונים פיננסיים"))

            c1, c2 = st.columns(2)
            c3, c4 = st.columns(2)
            c1.metric(t("m_pe"), fmt(pe) if pe else "—")
            c2.metric(t("m_mcap"), human_number(info.get("marketCap")))
            c3.metric(t("m_eps"), fmt(info.get("trailingEps")))
            _tgt = info.get("targetMeanPrice")
            c4.metric(t("m_target"), price_str(_tgt, currency) if _tgt else "—",
                      f"{(_tgt / price - 1) * 100:+.1f}%" if (_tgt and price) else None)

            st.markdown(
                f"**{company_name}** · {sector or '—'} · {industry or '—'} · "
                f"{info.get('exchange', '—')} · {currency or '—'}"
            )

            sections = financial_sections(info, price)
            _val_first = list(sections)[0] if sections else ""
            for title, rows in sections.items():
                vals = [str(v) for v in rows.values()]
                if all(v in ("—", "nan", "None", "") for v in vals):
                    continue
                with st.expander(title, expanded=(title == _val_first)):
                    st.table(pd.DataFrame({_PARAM: list(rows), _VAL: vals}).set_index(_PARAM))

            if not info or len(info) < 5:
                st.warning(L(
                    'Yahoo Finance החזיר מידע חברה חלקי או ריק. נסה שוב בעוד דקה, '
                    'או ראה את מקור SEC EDGAR למטה (למניות ארה"ב).'))

            # --- מקור עצמאי #2: SEC EDGAR ---
            st.markdown(L("### 🏛️ מקור עצמאי: SEC EDGAR (דוחות רשמיים)"))
            sec_df, (sec_tpl, sec_val) = get_sec_facts(symbol)
            if sec_df is not None and not sec_df.empty:
                show = (sec_df.rename(index=lambda x: L(x))
                        .map(lambda v: human_number(v) if isinstance(v, (int, float)) else v))
                st.table(show)
            st.caption(L(sec_tpl, x=sec_val) if sec_val is not None else L(sec_tpl))

            # --- דוחות כספיים מלאים (yfinance) ---
            st.markdown(L("### 📑 דוחות כספיים מלאים"))
            statements = get_statements(symbol)
            if statements:
                for label, sdf in statements.items():
                    with st.expander(L(label)):
                        show = sdf.map(
                            lambda v: human_number(v)
                            if isinstance(v, (int, float)) and pd.notna(v) else v
                        )
                        st.dataframe(show, use_container_width=True)
            else:
                st.caption(L("לא התקבלו דוחות כספיים עבור סימול זה."))

            st.caption(L(
                "מקורות: נתוני מחיר — {a} · מכפילים ותחזיות — Yahoo Finance · "
                "דוחות רשמיים — SEC EDGAR (data.sec.gov). "
                "ערכים ממקורות שונים עשויים להיות מעודכנים לתאריכים שונים.",
                a=price_source or "Yahoo Finance"))

    # --- ניתוח טכני ---
    with tab_tech:
        getattr(st, kind)(t("tech_summary_line", icon=icon, v=verdict_txt, s=f"{score:+d}"))
        st.caption(t("tech_caption"))

        st.markdown(t("tech_values_head"))
        tech_vals = {
            L("מחיר סגירה אחרון"): fmt(latest["Close"]),
            L("ממוצע נע 50"): fmt(latest["SMA50"]),
            L("ממוצע נע 100"): fmt(latest["SMA100"]),
            L("ממוצע נע 200"): fmt(latest["SMA200"]),
            "RSI (14)": fmt(latest["RSI"]),
            "MACD": fmt(latest["MACD"], digits=3),
            L("קו סיגנל MACD"): fmt(latest["MACD_signal"], digits=3),
            L("היסטוגרמת MACD"): fmt(latest["MACD_hist"], digits=3),
            L("בולינגר — עליון"): fmt(latest["BB_high"]),
            L("בולינגר — אמצע"): fmt(latest["BB_mid"]),
            L("בולינגר — תחתון"): fmt(latest["BB_low"]),
        }
        for label, key, dg in (
            ("סטוכסטי %K", "STOCH_K", 1), ("סטוכסטי %D", "STOCH_D", 1),
            ("ADX (14) — עוצמת מגמה", "ADX", 1),
            ("ATR (14)", "ATR", 2), ("ATR כאחוז מהמחיר", "ATR_pct", 2),
            ("OBV — מאזן נפח", "OBV", 0),
        ):
            if key in latest and is_num(latest.get(key)):
                tech_vals[L(label)] = (human_number(latest[key]) if key == "OBV"
                                       else fmt(latest[key], digits=dg))
        tech_df = pd.DataFrame(
            {L("אינדיקטור"): list(tech_vals.keys()), L("ערך"): list(tech_vals.values())}
        )
        st.dataframe(tech_df, hide_index=True, use_container_width=True)

        st.markdown(t("tech_signals_head"))
        st.dataframe(signals_df, hide_index=True, use_container_width=True)

    # --- גרפים ---
    with tab_chart:
        fig = build_chart(df, symbol, dark=dark, lang=chart_lang, chart_type=chart_type,
                          compact=compact_chart, overlays=overlays_on)
        st.plotly_chart(fig, use_container_width=True, config={
            "responsive": True, "displaylogo": False,
            "modeBarButtonsToAdd": ["drawline", "drawopenpath", "drawrect",
                                    "drawcircle", "eraseshape"],
        })
        st.caption(t("chart_caption", n=220 if compact_chart else 400))

    # --- השוואה מול מניות אחרות ---
    if tab_cmp is not None:
        with tab_cmp:
            render_compare(symbol, df, period, compare_syms, dark, compact=compact_chart)

    # --- נתונים גולמיים ---
    with tab_raw:
        st.dataframe(df.tail(300), use_container_width=True)
        csv = df.to_csv().encode("utf-8-sig")
        st.download_button(t("raw_download"), data=csv, file_name=f"{symbol}_analysis.csv",
                           mime="text/csv")

    st.divider()
    st.caption(t("disc_footer"))


if __name__ == "__main__":
    main()
