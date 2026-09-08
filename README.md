# 📈 מנתח מניות — ניתוח טכני ופיננסי (Streamlit)

אפליקציית פייתון מקומית לניתוח מניות, שרצה בדפדפן. **חינמית לחלוטין** — ללא מפתחות API, ללא מנויים, ללא שירותים בתשלום.

הנתונים נשלפים מ‑Yahoo Finance דרך הספרייה החינמית [`yfinance`](https://pypi.org/project/yfinance/), האינדיקטורים מחושבים עם ספריית הקוד הפתוח [`ta`](https://pypi.org/project/ta/), והגרפים מצוירים עם [`plotly`](https://pypi.org/project/plotly/) (אינטראקטיביים). תרגום אופציונלי לעברית דרך [`deep-translator`](https://pypi.org/project/deep-translator/) (שירות חינמי).

---

## מה האפליקציה עושה

| תחום | פירוט |
|------|-------|
| **קלט** | שדה **סימול או שם חברה** (`AAPL`, וגם `NVIDIA` → `NVDA` אוטומטית), בחירת טווח נתונים, כפתור "נתח מניה", כפתור **איפוס** |
| **נתונים פיננסיים** | שם החברה, סקטור, שווי שוק, **מכפיל רווח P/E** (כולל fallback מחושב מ‑EPS), Forward P/E, PEG, EPS, תשואת דיבידנד, P/S, P/B, בטא, שיא/שפל 52 שבועות ועוד |
| **אינדיקטורים טכניים** | ממוצעים נעים 50 / 100 / 200, RSI(14), MACD(12,26,9), רצועות בולינגר(20,2) |
| **גרפים** | גרף Plotly אינטראקטיבי: מחיר + ממוצעים + בולינגר, מחזור, RSI, MACD — עם זום, hover ומקרא. תוויות בעברית או באנגלית (מתג) |
| **סיכום טכני אוטומטי** | דירוג **Bullish / Bearish / Neutral** לפי ניקוד משוקלל, עם טבלת פירוט |
| **כדאיות קנייה** | פסק "שווה לקנות?" ולאיזה **טווח** (קצר / בינוני / ארוך), כל טווח משוקלל מאינדיקטורים מתאימים |
| **מצב יום / לילה** | מתג בסרגל הצד. למצב לילה מלא של המערכת: תפריט ☰ → Settings → Theme → Dark |
| **תרגום לעברית** | מתג בסרגל הצד — מתרגם סקטור, תעשייה ותיאור החברה מאנגלית |
| **ייצוא** | הורדת כל הנתונים והאינדיקטורים כקובץ CSV |

---

## הפעלה — הדרך הקלה (Windows)

1. ודא שמותקן **Python 3.10 ומעלה** ([הורדה](https://www.python.org/downloads/) — סמן בהתקנה "Add python.exe to PATH").
2. לחיצה כפולה על **`run.bat`**.

בפעם הראשונה זה יתקין את הספריות (דקה–שתיים). בכל פעם הבאה האפליקציה פשוט נפתחת בדפדפן בכתובת `http://localhost:8501`.

> אין צורך לגעת בקוד אף פעם. לעצירה — סגור את חלון הטרמינל שנפתח.

### חלופה: PowerShell

```powershell
.\run.ps1
```

אם PowerShell חוסם סקריפטים, הרץ פעם אחת:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

## הפעלה ידנית (כל מערכת הפעלה)

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

הדפדפן ייפתח אוטומטית. אם לא — היכנס ל‑`http://localhost:8501`.

---

## מבנה הפרויקט

```
app.py                  קוד האפליקציה
requirements.txt        רשימת הספריות
.streamlit/config.toml  עיצוב בסיסי
run.bat                 הפעלה בלחיצה כפולה (Windows)
run.ps1                 הפעלה מ-PowerShell
.gitignore              קבצים שלא נשמרים ב-Git
README.md               הקובץ הזה
```

---

## פרסום אונליין (חינם) — נגיש מכל מחשב וטלפון

הדרך המומלצת: **Streamlit Community Cloud** — נותן כתובת קבועה כמו
`https://my-stock-analyzer.streamlit.app`, עובד בטלפון, והמחשב שלך לא צריך להישאר דלוק.
הכל חינמי לחלוטין (GitHub חינמי + Streamlit Cloud חינמי, בלי כרטיס אשראי).

### שלב א' — חשבון GitHub והעלאת הקוד

1. אם אין לך חשבון: היכנס ל‑<https://github.com/signup> ופתח חשבון חינמי.
2. צור מאגר חדש ב‑<https://github.com/new>:
   - **Repository name:** `stock-analyzer` (או כל שם)
   - אפשר להשאיר **Public** (ציבורי) — זה בסדר, אין כאן סודות. אפשר גם **Private**.
   - אל תסמן "Add a README" (כבר יש לנו).
   - לחץ **Create repository**.
3. בתיקיית הפרויקט כבר יש מאגר Git מקומי עם commit ראשון. חבר אותו ל‑GitHub —
   העתק את הכתובת שגיטהאב מציג (משהו כמו `https://github.com/USERNAME/stock-analyzer.git`)
   והרץ ב‑PowerShell מתוך תיקיית הפרויקט:

   ```powershell
   git remote add origin https://github.com/USERNAME/stock-analyzer.git
   git branch -M main
   git push -u origin main
   ```

   בפעם הראשונה GitHub יבקש להתחבר בדפדפן — אשר.

### שלב ב' — פריסה ב‑Streamlit Community Cloud

1. היכנס ל‑<https://share.streamlit.io> ולחץ **Sign in with GitHub** (חינמי).
2. לחץ **Create app** → **Deploy a public app from GitHub**.
3. מלא:
   - **Repository:** `USERNAME/stock-analyzer`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** בחר שם (זו הכתובת הסופית).
4. לחץ **Deploy**. הבנייה לוקחת 1–3 דקות, ואז מקבלים כתובת קבועה.
5. **שיתוף:** פשוט שולחים את הכתובת לחברים בוואטסאפ/מייל. נפתח בכל דפדפן, כולל טלפון.

### עדכון האפליקציה בעתיד

כל שינוי בקוד — פשוט דוחפים ל‑GitHub, ו‑Streamlit Cloud מעדכן אוטומטית:

```powershell
git add -A
git commit -m "עדכון"
git push
```

### הערות לגרסת הענן

- **שינה:** אפליקציה ציבורית בחינם "נרדמת" אחרי ~שבוע ללא כניסות ומתעוררת תוך ~30 שניות בכניסה הבאה.
- **הגבלת קצב של Yahoo:** בענן, כתובת ה‑IP משותפת, ולעיתים Yahoo חוסם זמנית. באפליקציה יש ניסיונות חוזרים אוטומטיים; אם בכל זאת מופיעה שגיאה — להמתין דקה וללחוץ שוב "נתח מניה".

### חלופה בלי GitHub — Hugging Face Spaces

1. פתח חשבון חינמי ב‑<https://huggingface.co/join>.
2. <https://huggingface.co/new-space> → בחר SDK = **Streamlit**, שם, ו‑**Public**.
3. בלשונית **Files** של ה‑Space העלה את `app.py`, `requirements.txt` ותיקיית `.streamlit`.
4. ה‑Space בונה את עצמו ונותן כתובת קבועה `huggingface.co/spaces/USERNAME/שם-הספייס`.

---

## הערות

- **מטמון**: נתונים נשמרים במטמון למשך שעה כדי להאיץ ניתוחים חוזרים. להרעננה — לחץ שוב על "נתח מניה" אחרי שהמטמון פג, או הפעל מחדש.
- **סימולים לא אמריקאיים**: אפשר להזין סיומת בורסה, למשל `TEVA.TA` (ת"א), `SAP.DE` (פרנקפורט), `SHOP.TO` (טורונטו).
- **מידע חברה חלקי**: לעיתים Yahoo מחזיר `info` ריק לחלק מהסימולים. נתוני המחיר והאינדיקטורים עדיין תקינים במקרה כזה.
- ⚠️ הכלי מיועד ללימוד ולמחקר בלבד ואינו מהווה ייעוץ השקעות.
