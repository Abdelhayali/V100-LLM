@echo off
rem Qwen3.8-27B PXQ3 - 8k context, vision on GPU (kernel: pxa)
rem ~27 tok/s gen
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\pxa"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\llama-server.exe" ( echo Kernel pxa missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\llama-server.exe" ^
  -m "%M%\Qwen3.8-27B-PXQ3-GGUF.gguf" ^
  --mmproj "%M%\mmproj-Qwen3.8-27B-Q8_0.gguf" ^
  -ngl 99 ^
  -c 8192 ^
  -np 1 ^
  -fa on ^
  --jinja ^
  --reasoning off ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
