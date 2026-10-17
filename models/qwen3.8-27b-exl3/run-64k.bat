@echo off
rem Qwen3.8-27B EXL3 3.0bpw (SC, ExLlamaV3) - 64k context, Q4 cache, vision (kernel: exllamav3)
rem ~11.5 tok/s gen, 13.8 GB VRAM at 64k (Q4 cache); text + image OK
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\exllamav3"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\tabbyAPI\main.py" ( echo Kernel exllamav3 missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\tabbyAPI\main.py" ^
  -m "%M%\config.json" ^
  max_seq_len 65536 ^
  cache_size 65536 ^
  cache_mode Q4 ^
  vision true ^
  reasoning true ^
  chunk_size 2048 ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
