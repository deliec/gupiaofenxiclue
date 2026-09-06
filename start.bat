@echo off
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
set "USERPROFILE=%~dp0"
set "HOME=%~dp0"
echo ============================================
echo   Stock Analysis System starting...
echo   Open browser: http://localhost:8501
echo ============================================
venv\Scripts\streamlit.exe run app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
pause
