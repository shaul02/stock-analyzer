# הפעלה מ-PowerShell:  .\run.ps1
# אם PowerShell חוסם סקריפטים, הרץ פעם אחת:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[1/3] יוצר סביבה וירטואלית..." -ForegroundColor Cyan
    python -m venv .venv
}

$py = ".\.venv\Scripts\python.exe"

Write-Host "[2/3] מתקין / מעדכן ספריות..." -ForegroundColor Cyan
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r requirements.txt

Write-Host "[3/3] מפעיל את האפליקציה בדפדפן..." -ForegroundColor Green
& $py -m streamlit run app.py
