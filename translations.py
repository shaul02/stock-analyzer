"""תרגומי עומק: מיפוי מחרוזת המקור (עברית) -> {en, ru}.

מחרוזת שאין לה ערך כאן נשארת בעברית. הפונקציה L() ב-app.py משתמשת במילון הזה.
מפתחות עם {x} הם תבניות שמקבלים .format(x=...).
"""

DEEP: dict[str, dict[str, str]] = {
    # ---------- financial_sections: כותרות ----------
    "הערכת שווי (Valuation)": {"en": "Valuation", "ru": "Оценка (Valuation)"},
    "רווחיות (Profitability)": {"en": "Profitability", "ru": "Рентабельность"},
    "צמיחה (Growth)": {"en": "Growth", "ru": "Рост"},
    "איתנות פיננסית (Balance Sheet)": {"en": "Balance sheet strength", "ru": "Баланс / устойчивость"},
    "דיבידנד": {"en": "Dividend", "ru": "Дивиденды"},
    "תחזית אנליסטים": {"en": "Analyst view", "ru": "Прогноз аналитиков"},
    "מניה ומסחר": {"en": "Share & trading", "ru": "Акция и торги"},
    # ---------- financial_sections: תוויות ----------
    "שווי שוק": {"en": "Market cap", "ru": "Капитализация"},
    "שווי מיזם (EV)": {"en": "Enterprise value (EV)", "ru": "Стоимость предприятия (EV)"},
    "מכפיל רווח נגרר (P/E)": {"en": "Trailing P/E", "ru": "P/E (за 12 мес.)"},
    "מכפיל רווח עתידי (Fwd P/E)": {"en": "Forward P/E", "ru": "Форвардный P/E"},
    "מכפיל PEG": {"en": "PEG ratio", "ru": "PEG"},
    "מחיר / מכירות (P/S)": {"en": "Price / sales (P/S)", "ru": "Цена / выручка (P/S)"},
    "מחיר / הון עצמי (P/B)": {"en": "Price / book (P/B)", "ru": "Цена / капитал (P/B)"},
    "EV / הכנסות": {"en": "EV / revenue", "ru": "EV / выручка"},
    "מחיר / תזרים חופשי (P/FCF)": {"en": "Price / free cash flow", "ru": "Цена / своб. ден. поток"},
    "שולי רווח גולמי": {"en": "Gross margin", "ru": "Валовая маржа"},
    "שולי רווח תפעולי": {"en": "Operating margin", "ru": "Операционная маржа"},
    "שולי רווח נקי": {"en": "Net margin", "ru": "Чистая маржа"},
    "שולי EBITDA": {"en": "EBITDA margin", "ru": "Маржа EBITDA"},
    "תשואה על ההון (ROE)": {"en": "Return on equity (ROE)", "ru": "Рентабельность капитала (ROE)"},
    "תשואה על הנכסים (ROA)": {"en": "Return on assets (ROA)", "ru": "Рентабельность активов (ROA)"},
    "צמיחת הכנסות (שנתי)": {"en": "Revenue growth (YoY)", "ru": "Рост выручки (г/г)"},
    "צמיחת רווח (שנתי)": {"en": "Earnings growth (YoY)", "ru": "Рост прибыли (г/г)"},
    "צמיחת רווח רבעוני (YoY)": {"en": "Quarterly earnings growth (YoY)", "ru": "Рост прибыли за квартал (г/г)"},
    "הכנסות 12 חודשים": {"en": "Revenue (TTM)", "ru": "Выручка (12 мес.)"},
    "רווח נקי (12 ח')": {"en": "Net income (TTM)", "ru": "Чистая прибыль (12 мес.)"},
    "מזומן ושווי מזומן": {"en": "Cash & equivalents", "ru": "Денежные средства"},
    "חוב כולל": {"en": "Total debt", "ru": "Совокупный долг"},
    "חוב נטו": {"en": "Net debt", "ru": "Чистый долг"},
    "יחס חוב להון (D/E)": {"en": "Debt / equity", "ru": "Долг / капитал (D/E)"},
    "יחס שוטף (Current)": {"en": "Current ratio", "ru": "Коэф. текущей ликвидности"},
    "יחס מהיר (Quick)": {"en": "Quick ratio", "ru": "Коэф. быстрой ликвидности"},
    "מזומן למניה": {"en": "Cash per share", "ru": "Денежные средства на акцию"},
    "תזרים חופשי (FCF)": {"en": "Free cash flow", "ru": "Свободный ден. поток"},
    "תזרים תפעולי": {"en": "Operating cash flow", "ru": "Операционный ден. поток"},
    "דיבידנד למניה (שנתי)": {"en": "Dividend per share (annual)", "ru": "Дивиденд на акцию (год)"},
    "תשואת דיבידנד": {"en": "Dividend yield", "ru": "Дивидендная доходность"},
    "תשואה ממוצעת 5 שנים": {"en": "5-year avg. yield", "ru": "Средняя доходность за 5 лет"},
    "יחס חלוקה (Payout)": {"en": "Payout ratio", "ru": "Коэф. выплат (Payout)"},
    "המלצה": {"en": "Recommendation", "ru": "Рекомендация"},
    "מספר אנליסטים": {"en": "Analysts covering", "ru": "Число аналитиков"},
    "מחיר יעד ממוצע": {"en": "Avg. price target", "ru": "Средний таргет"},
    "מחיר יעד גבוה": {"en": "High price target", "ru": "Верхний таргет"},
    "מחיר יעד נמוך": {"en": "Low price target", "ru": "Нижний таргет"},
    "פוטנציאל מול מחיר נוכחי": {"en": "Upside vs. current price", "ru": "Потенциал к текущей цене"},
    "מניות במחזור": {"en": "Shares outstanding", "ru": "Акций в обращении"},
    "מניות חופשיות (Float)": {"en": "Free float", "ru": "Free float"},
    "אחזקת מוסדיים": {"en": "Institutional ownership", "ru": "Доля институционалов"},
    "פוזיציות שורט (% מ-Float)": {"en": "Short interest (% of float)", "ru": "Шорт (% от float)"},
    "בטא (Beta)": {"en": "Beta", "ru": "Бета"},
    "טווח 52 שבועות": {"en": "52-week range", "ru": "Диапазон за 52 недели"},
    "מחזור מסחר ממוצע": {"en": "Avg. trading volume", "ru": "Средний объём торгов"},
    # ---------- crypto_sections ----------
    "נתוני מטבע": {"en": "Coin data", "ru": "Данные монеты"},
    "היצע במחזור": {"en": "Circulating supply", "ru": "Циркулирующее предложение"},
    "היצע מרבי / כולל": {"en": "Max / total supply", "ru": "Макс. / общее предложение"},
    "אחוז מההיצע המרבי": {"en": "% of max supply", "ru": "% от макс. предложения"},
    "נפח מסחר 24 שעות": {"en": "24h trading volume", "ru": "Объём за 24 ч"},
    "מטבע התייחסות": {"en": "Quote currency", "ru": "Валюта котировки"},
    "אלגוריתם": {"en": "Algorithm", "ru": "Алгоритм"},
    # ---------- get_statements ----------
    "דוח רווח והפסד (שנתי)": {"en": "Income statement (annual)", "ru": "Отчёт о прибылях (год)"},
    "דוח רווח והפסד (רבעוני)": {"en": "Income statement (quarterly)", "ru": "Отчёт о прибылях (кв.)"},
    "מאזן (שנתי)": {"en": "Balance sheet (annual)", "ru": "Баланс (год)"},
    "מאזן (רבעוני)": {"en": "Balance sheet (quarterly)", "ru": "Баланс (кв.)"},
    "תזרים מזומנים (שנתי)": {"en": "Cash flow (annual)", "ru": "Ден. потоки (год)"},
    "תזרים מזומנים (רבעוני)": {"en": "Cash flow (quarterly)", "ru": "Ден. потоки (кв.)"},
    # ---------- SEC ----------
    "הכנסות": {"en": "Revenue", "ru": "Выручка"},
    "רווח נקי": {"en": "Net income", "ru": "Чистая прибыль"},
    "רווח תפעולי": {"en": "Operating income", "ru": "Операционная прибыль"},
    "סך נכסים": {"en": "Total assets", "ru": "Всего активов"},
    "סך התחייבויות": {"en": "Total liabilities", "ru": "Всего обязательств"},
    "הון עצמי": {"en": "Stockholders' equity", "ru": "Собственный капитал"},
    "רווח למניה מדולל": {"en": "Diluted EPS", "ru": "Разводнённая EPS"},
    'לא נמצאה חברה אמריקאית תואמת ב-SEC EDGAR (רלוונטי למניות בארה"ב).': {
        "en": "No matching US company in SEC EDGAR (US-listed stocks only).",
        "ru": "Компания не найдена в SEC EDGAR (только акции США).",
    },
    "קריאת SEC EDGAR נכשלה: {x}": {
        "en": "SEC EDGAR request failed: {x}", "ru": "Запрос к SEC EDGAR не удался: {x}",
    },
    "SEC EDGAR: לא נמצאו נתוני דוח שנתי במבנה צפוי.": {
        "en": "SEC EDGAR: no annual-report data in the expected shape.",
        "ru": "SEC EDGAR: годовые данные в ожидаемом формате не найдены.",
    },
    "מקור: SEC EDGAR · CIK {x} · דוחות 10-K/20-F רשמיים.": {
        "en": "Source: SEC EDGAR · CIK {x} · official 10-K/20-F filings.",
        "ru": "Источник: SEC EDGAR · CIK {x} · официальные отчёты 10-K/20-F.",
    },
    # ---------- טבלאות: עמודות ----------
    "פרמטר": {"en": "Parameter", "ru": "Параметр"},
    "ערך": {"en": "Value", "ru": "Значение"},
    "אינדיקטור": {"en": "Indicator", "ru": "Индикатор"},
    "איתות": {"en": "Signal", "ru": "Сигнал"},
    "פירוש": {"en": "Meaning", "ru": "Пояснение"},
    "חיובי ▲": {"en": "Positive ▲", "ru": "Плюс ▲"},
    "שלילי ▼": {"en": "Negative ▼", "ru": "Минус ▼"},
    "ניטרלי ◆": {"en": "Neutral ◆", "ru": "Нейтр. ◆"},
    "מידע": {"en": "Info", "ru": "Инфо"},
    "אין מספיק נתונים": {"en": "not enough data", "ru": "недостаточно данных"},
    # ---------- technical_summary: תוויות אינדיקטור ----------
    "מחיר מול ממוצע נע 50": {"en": "Price vs. MA(50)", "ru": "Цена против MA(50)"},
    "מחיר מול ממוצע נע 100": {"en": "Price vs. MA(100)", "ru": "Цена против MA(100)"},
    "מחיר מול ממוצע נע 200": {"en": "Price vs. MA(200)", "ru": "Цена против MA(200)"},
    "צלב זהב / צלב מוות (50 מול 200)": {"en": "Golden / death cross (50 vs 200)",
                                        "ru": "Золотой / мёртвый крест (50 и 200)"},
    "MACD מול קו הסיגנל": {"en": "MACD vs. signal line", "ru": "MACD против сигнальной линии"},
    "רצועות בולינגר": {"en": "Bollinger Bands", "ru": "Полосы Боллинджера"},
    "RSI (14)": {"en": "RSI (14)", "ru": "RSI (14)"},
    "RSI (14) = {x}": {"en": "RSI (14) = {x}", "ru": "RSI (14) = {x}"},
    "סטוכסטי %K = {x}": {"en": "Stochastic %K = {x}", "ru": "Стохастик %K = {x}"},
    "ADX (14) = {x}": {"en": "ADX (14) = {x}", "ru": "ADX (14) = {x}"},
    "ATR = {x}% מהמחיר": {"en": "ATR = {x}% of price", "ru": "ATR = {x}% от цены"},
    # ---------- technical_summary: פירושים ----------
    "המחיר מעל ממוצע 50 יום": {"en": "Price is above the 50-day MA", "ru": "Цена выше MA за 50 дней"},
    "המחיר מתחת לממוצע 50 יום": {"en": "Price is below the 50-day MA", "ru": "Цена ниже MA за 50 дней"},
    "המחיר מעל ממוצע 100 יום": {"en": "Price is above the 100-day MA", "ru": "Цена выше MA за 100 дней"},
    "המחיר מתחת לממוצע 100 יום": {"en": "Price is below the 100-day MA", "ru": "Цена ниже MA за 100 дней"},
    "המחיר מעל ממוצע 200 יום — מגמה ארוכת טווח חיובית": {
        "en": "Price above the 200-day MA — positive long-term trend",
        "ru": "Цена выше MA(200) — положительный долгосрочный тренд",
    },
    "המחיר מתחת לממוצע 200 יום — מגמה ארוכת טווח שלילית": {
        "en": "Price below the 200-day MA — negative long-term trend",
        "ru": "Цена ниже MA(200) — отрицательный долгосрочный тренд",
    },
    "ממוצע 50 מעל ממוצע 200 — 'צלב זהב'": {
        "en": "MA(50) above MA(200) — 'golden cross'", "ru": "MA(50) выше MA(200) — «золотой крест»",
    },
    "ממוצע 50 מתחת לממוצע 200 — 'צלב מוות'": {
        "en": "MA(50) below MA(200) — 'death cross'", "ru": "MA(50) ниже MA(200) — «мёртвый крест»",
    },
    "מכירת יתר — פוטנציאל לתיקון כלפי מעלה": {
        "en": "Oversold — potential for an upward bounce", "ru": "Перепроданность — возможен отскок вверх",
    },
    "קניית יתר — סיכון לתיקון כלפי מטה": {
        "en": "Overbought — risk of a pullback", "ru": "Перекупленность — риск отката вниз",
    },
    "בטווח מאוזן (30–70)": {"en": "In a balanced range (30–70)", "ru": "В сбалансированном диапазоне (30–70)"},
    "MACD מעל קו הסיגנל — מומנטום חיובי": {
        "en": "MACD above the signal line — positive momentum",
        "ru": "MACD выше сигнальной линии — положительный импульс",
    },
    "MACD מתחת לקו הסיגנל — מומנטום שלילי": {
        "en": "MACD below the signal line — negative momentum",
        "ru": "MACD ниже сигнальной линии — отрицательный импульс",
    },
    "המחיר מעל הרצועה העליונה — מתיחות/קניית יתר": {
        "en": "Price above the upper band — stretched / overbought",
        "ru": "Цена выше верхней полосы — перегрев / перекупленность",
    },
    "המחיר מתחת לרצועה התחתונה — מתיחות/מכירת יתר": {
        "en": "Price below the lower band — stretched / oversold",
        "ru": "Цена ниже нижней полосы — перегрев / перепроданность",
    },
    "המחיר בתוך הרצועות": {"en": "Price is inside the bands", "ru": "Цена внутри полос"},
    "מכירת יתר (מתחת ל-20)": {"en": "Oversold (below 20)", "ru": "Перепроданность (ниже 20)"},
    "קניית יתר (מעל 80)": {"en": "Overbought (above 80)", "ru": "Перекупленность (выше 80)"},
    "בטווח מאוזן (20–80)": {"en": "In a balanced range (20–80)", "ru": "В сбалансированном диапазоне (20–80)"},
    "מגמה חזקה": {"en": "strong trend", "ru": "сильный тренд"},
    "מגמה חלשה/דשדוש": {"en": "weak trend / range", "ru": "слабый тренд / боковик"},
    "מגמה מתגבשת": {"en": "trend forming", "ru": "тренд формируется"},
    "{x} — ADX מודד עוצמת מגמה, לא כיוון": {
        "en": "{x} — ADX measures trend strength, not direction",
        "ru": "{x} — ADX измеряет силу тренда, а не направление",
    },
    "תנודתיות יומית ממוצעת — שימושי לתמחור סטופ-לוס": {
        "en": "Average daily volatility — useful for sizing a stop-loss",
        "ru": "Средняя дневная волатильность — полезно для стоп-лосса",
    },
    # ---------- tech_vals ----------
    "מחיר סגירה אחרון": {"en": "Last close", "ru": "Последнее закрытие"},
    "ממוצע נע 50": {"en": "MA(50)", "ru": "MA(50)"},
    "ממוצע נע 100": {"en": "MA(100)", "ru": "MA(100)"},
    "ממוצע נע 200": {"en": "MA(200)", "ru": "MA(200)"},
    "MACD": {"en": "MACD", "ru": "MACD"},
    "קו סיגנל MACD": {"en": "MACD signal line", "ru": "Сигнальная линия MACD"},
    "היסטוגרמת MACD": {"en": "MACD histogram", "ru": "Гистограмма MACD"},
    "בולינגר — עליון": {"en": "Bollinger — upper", "ru": "Боллинджер — верх"},
    "בולינגר — אמצע": {"en": "Bollinger — middle", "ru": "Боллинджер — центр"},
    "בולינגר — תחתון": {"en": "Bollinger — lower", "ru": "Боллинджер — низ"},
    "סטוכסטי %K": {"en": "Stochastic %K", "ru": "Стохастик %K"},
    "סטוכסטי %D": {"en": "Stochastic %D", "ru": "Стохастик %D"},
    "ADX (14) — עוצמת מגמה": {"en": "ADX (14) — trend strength", "ru": "ADX (14) — сила тренда"},
    "ATR (14)": {"en": "ATR (14)", "ru": "ATR (14)"},
    "ATR כאחוז מהמחיר": {"en": "ATR as % of price", "ru": "ATR в % от цены"},
    "OBV — מאזן נפח": {"en": "OBV — on-balance volume", "ru": "OBV — балансовый объём"},
    # ---------- _horizon_*: נימוקים ----------
    "המחיר מעל ממוצע 20 יום": {"en": "Price above the 20-day MA", "ru": "Цена выше MA за 20 дней"},
    "המחיר מתחת לממוצע 20 יום": {"en": "Price below the 20-day MA", "ru": "Цена ниже MA за 20 дней"},
    "מומנטום MACD חיובי ומתחזק": {"en": "MACD momentum positive and rising",
                                  "ru": "Импульс MACD положительный и растёт"},
    "מומנטום MACD שלילי ומתחזק כלפי מטה": {"en": "MACD momentum negative and falling",
                                          "ru": "Импульс MACD отрицательный и падает"},
    "מומנטום MACD מעורב": {"en": "MACD momentum mixed", "ru": "Импульс MACD смешанный"},
    "RSI = {x} — מכירת יתר, אפשרות לתיקון מעלה": {
        "en": "RSI = {x} — oversold, an upward bounce is possible",
        "ru": "RSI = {x} — перепроданность, возможен отскок вверх",
    },
    "RSI = {x} — קניית יתר, סיכון לתיקון מטה": {
        "en": "RSI = {x} — overbought, risk of a pullback",
        "ru": "RSI = {x} — перекупленность, риск отката",
    },
    "RSI = {x} — חיובי בלי קיצון": {"en": "RSI = {x} — positive, not extreme",
                                    "ru": "RSI = {x} — положительно, без крайностей"},
    "RSI = {x} — חלש": {"en": "RSI = {x} — weak", "ru": "RSI = {x} — слабо"},
    "עלייה של {x}% ב-5 ימי מסחר אחרונים": {
        "en": "Up {x}% over the last 5 trading days", "ru": "Рост {x}% за последние 5 торговых дней",
    },
    "ירידה של {x}% ב-5 ימי מסחר אחרונים": {
        "en": "Down {x}% over the last 5 trading days", "ru": "Падение {x}% за последние 5 торговых дней",
    },
    "המחיר קרוב לרצועת בולינגר התחתונה": {
        "en": "Price near the lower Bollinger band", "ru": "Цена у нижней полосы Боллинджера",
    },
    "המחיר קרוב לרצועת בולינגר העליונה": {
        "en": "Price near the upper Bollinger band", "ru": "Цена у верхней полосы Боллинджера",
    },
    "המחיר מעל ממוצע {x} יום": {"en": "Price above the {x}-day MA", "ru": "Цена выше MA за {x} дней"},
    "המחיר מתחת לממוצע {x} יום": {"en": "Price below the {x}-day MA", "ru": "Цена ниже MA за {x} дней"},
    "ממוצע 50 יום במגמת עלייה": {"en": "50-day MA is rising", "ru": "MA(50) растёт"},
    "ממוצע 50 יום במגמת ירידה": {"en": "50-day MA is falling", "ru": "MA(50) падает"},
    "ממוצע 50 מעל ממוצע 100": {"en": "MA(50) above MA(100)", "ru": "MA(50) выше MA(100)"},
    "ממוצע 50 מתחת לממוצע 100": {"en": "MA(50) below MA(100)", "ru": "MA(50) ниже MA(100)"},
    "MACD מעל קו האפס": {"en": "MACD above the zero line", "ru": "MACD выше нулевой линии"},
    "MACD מתחת לקו האפס": {"en": "MACD below the zero line", "ru": "MACD ниже нулевой линии"},
    "עלייה של {x}% בחודש האחרון": {"en": "Up {x}% over the past month", "ru": "Рост {x}% за последний месяц"},
    "ירידה של {x}% בחודש האחרון": {"en": "Down {x}% over the past month",
                                   "ru": "Падение {x}% за последний месяц"},
    "המחיר מעל ממוצע 200 יום": {"en": "Price above the 200-day MA", "ru": "Цена выше MA за 200 дней"},
    "המחיר מתחת לממוצע 200 יום": {"en": "Price below the 200-day MA", "ru": "Цена ниже MA за 200 дней"},
    "המחיר מתוח מאוד מעל ממוצע 200 יום (סיכון תיקון)": {
        "en": "Price stretched well above the 200-day MA (pullback risk)",
        "ru": "Цена сильно оторвалась вверх от MA(200) (риск отката)",
    },
    "'צלב זהב' — ממוצע 50 מעל ממוצע 200": {
        "en": "'Golden cross' — MA(50) above MA(200)", "ru": "«Золотой крест» — MA(50) выше MA(200)",
    },
    "'צלב מוות' — ממוצע 50 מתחת לממוצע 200": {
        "en": "'Death cross' — MA(50) below MA(200)", "ru": "«Мёртвый крест» — MA(50) ниже MA(200)",
    },
    "ממוצע 200 יום במגמת עלייה": {"en": "200-day MA is rising", "ru": "MA(200) растёт"},
    "ממוצע 200 יום במגמת ירידה": {"en": "200-day MA is falling", "ru": "MA(200) падает"},
    "קרוב לשיא 52 שבועות — מגמה חזקה": {
        "en": "Near the 52-week high — strong trend", "ru": "Близко к максимуму за 52 недели — сильный тренд",
    },
    "קרוב לשפל 52 שבועות — חולשה": {
        "en": "Near the 52-week low — weakness", "ru": "Близко к минимуму за 52 недели — слабость",
    },
    "החברה מפסידה (P/E שלילי)": {"en": "Company is unprofitable (negative P/E)",
                                 "ru": "Компания убыточна (отрицательный P/E)"},
    "מכפיל רווח סביר (P/E ≈ {x})": {"en": "Reasonable P/E (≈ {x})", "ru": "Разумный P/E (≈ {x})"},
    "מכפיל רווח גבוה (P/E ≈ {x})": {"en": "High P/E (≈ {x})", "ru": "Высокий P/E (≈ {x})"},
    "מכפיל רווח גבוה מאוד (P/E ≈ {x})": {"en": "Very high P/E (≈ {x})", "ru": "Очень высокий P/E (≈ {x})"},
    "PEG ≈ {x} — צמיחה אטרקטיבית מול המחיר": {
        "en": "PEG ≈ {x} — growth attractive vs. price", "ru": "PEG ≈ {x} — рост привлекателен к цене",
    },
    "PEG ≈ {x} — יקר יחסית לצמיחה": {
        "en": "PEG ≈ {x} — expensive relative to growth", "ru": "PEG ≈ {x} — дорого относительно роста",
    },
    # ---------- fund/crypto tabs ----------
    "נתונים פיננסיים": {"en": "Financials", "ru": "Финансы"},
    'Yahoo Finance החזיר מידע חברה חלקי או ריק. נסה שוב בעוד דקה, או ראה את מקור SEC EDGAR למטה (למניות ארה"ב).': {
        "en": "Yahoo Finance returned partial or empty company info. Retry in a minute, "
              "or see the SEC EDGAR source below (US stocks).",
        "ru": "Yahoo Finance вернул неполные данные компании. Повторите через минуту "
              "или см. источник SEC EDGAR ниже (акции США).",
    },
    "### 🏛️ מקור עצמאי: SEC EDGAR (דוחות רשמיים)": {
        "en": "### 🏛️ Independent source: SEC EDGAR (official filings)",
        "ru": "### 🏛️ Независимый источник: SEC EDGAR (офиц. отчёты)",
    },
    "### 📑 דוחות כספיים מלאים": {
        "en": "### 📑 Full financial statements", "ru": "### 📑 Полная финансовая отчётность",
    },
    "לא התקבלו דוחות כספיים עבור סימול זה.": {
        "en": "No financial statements were returned for this symbol.",
        "ru": "Финансовая отчётность для этого тикера не получена.",
    },
    "מקורות: נתוני מחיר — {a} · מכפילים ותחזיות — Yahoo Finance · דוחות רשמיים — SEC EDGAR (data.sec.gov). ערכים ממקורות שונים עשויים להיות מעודכנים לתאריכים שונים.": {
        "en": "Sources: prices — {a} · ratios & forecasts — Yahoo Finance · official filings — "
              "SEC EDGAR (data.sec.gov). Values from different sources may be as of different dates.",
        "ru": "Источники: цены — {a} · мультипликаторы и прогнозы — Yahoo Finance · офиц. отчёты — "
              "SEC EDGAR (data.sec.gov). Данные из разных источников могут быть на разные даты.",
    },
    "נתוני מטבע — {a}": {"en": "Coin data — {a}", "ru": "Данные монеты — {a}"},
    "מדובר במטבע קריפטו. נתוני יסוד של חברה (מכפיל רווח, דוחות כספיים, תחזיות אנליסטים, SEC) אינם רלוונטיים; מוצגים נתוני היצע, שווי שוק ונפח מסחר.": {
        "en": "This is a cryptocurrency. Company fundamentals (P/E, statements, analyst targets, SEC) "
              "don't apply; supply, market cap and trading volume are shown instead.",
        "ru": "Это криптовалюта. Фундаментал компании (P/E, отчётность, таргеты, SEC) неприменим; "
              "показаны предложение, капитализация и объём торгов.",
    },
    "מקורות: נתוני מחיר ומטבע — {a} (CoinMarketCap דרך yfinance). ניתוח טכני מלא זמין בכרטיסייה 'ניתוח טכני'.": {
        "en": "Sources: price & coin data — {a} (CoinMarketCap via yfinance). "
              "Full technical analysis is in the 'Technicals' tab.",
        "ru": "Источники: цена и данные монеты — {a} (CoinMarketCap через yfinance). "
              "Полный теханализ — во вкладке «Теханализ».",
    },
}
