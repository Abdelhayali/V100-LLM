@echo off
rem Scores models with the V100-LLM test suite and rebuilds eval\results\leaderboard.html/.png.
rem   EVALUATE.bat                    all installed models not yet scored
rem   EVALUATE.bat saluki-27b         one model (its first preset)
rem   EVALUATE.bat saluki-27b:262k    one preset;  add --redo to score again
cd /d "%~dp0"
set "PY=%~dp0runtime\python\python.exe"
if not exist "%PY%" set "PY=python"
powershell -NoProfile -Command "try { Invoke-RestMethod http://127.0.0.1:7860/api/status -TimeoutSec 3 | Out-Null } catch { exit 1 }" || (start "V100-LLM" "%PY%" gui\launcher.py --no-browser & timeout /t 4 >nul)
"%PY%" eval\run_all.py %*
start "" "%~dp0eval\results\leaderboard.html"
pause
