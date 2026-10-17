@echo off
rem Strata: Qwen3.8-Flash-Next 125B IQ2_XS - Coder IQ1_M (half the experts, coding), 262k, vision on CPU (kernel: strata)
rem Open http://127.0.0.1:%PORT% (default 8899).
"%~dp0..\..\runtime\python\python.exe" "%~dp0..\..\gui\launcher.py" --serve strata-flash-next:coder-iq1m
if errorlevel 1 pause
