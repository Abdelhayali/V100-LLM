@echo off
rem Switches the Tesla V100 back to TCC (compute-only mode, the original setting). Run as Administrator, then REBOOT.
net session >nul 2>&1 || (echo Please right-click this file and choose "Run as administrator". & pause & exit /b 1)
nvidia-smi -i 0 -dm 1
echo.
nvidia-smi --query-gpu=name,driver_model.current,driver_model.pending --format=csv
echo.
echo Done. "pending" should say TCC. Restart Windows now to apply it.
pause
