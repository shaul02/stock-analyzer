@echo off
REM ============================================================
REM  הפעלה בלחיצה כפולה. בפעם הראשונה יותקנו הספריות (דקה-שתיים),
REM  בכל פעם הבאה האפליקציה פשוט תיפתח בדפדפן.
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] יוצר סביבה וירטואלית...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo לא נמצא Python. התקן מ- https://www.python.org/downloads/ ובחר "Add python.exe to PATH".
        pause
        exit /b 1
    )
)

echo [2/3] מתקין / מעדכן ספריות...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo התקנת הספריות נכשלה. בדוק חיבור אינטרנט ונסה שוב.
    pause
    exit /b 1
)

echo [3/3] מפעיל את האפליקציה בדפדפן...
".venv\Scripts\python.exe" -m streamlit run app.py

pause
