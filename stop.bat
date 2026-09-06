@echo off
echo ============================================
echo   Stopping Stock Analysis System...
echo ============================================
powershell -NoProfile -Command "$p = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -ne 0 } | Select-Object -ExpandProperty OwningProcess -Unique; if ($p) { Stop-Process -Id $p -Force; Write-Host 'Stopped process(es):' $p } else { Write-Host 'No process running on port 8501' }"
echo Done.
pause
