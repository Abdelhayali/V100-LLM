@echo off
rem Qwen3.8-27B HauhauCS Aggressive IQ3_XS - FastMTP, 24k context (kernel: fastmtp)
rem 40-53 tok/s gen
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\fastmtp"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\llama-server.exe" ( echo Kernel fastmtp missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\llama-server.exe" ^
  -m "%M%\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ3_XS.gguf" ^
  --mmproj "%M%\mmproj-Qwen3.8-27B-Q8_0.gguf" ^
  --spec-type draft-mtp ^
  --spec-draft-model "%M%\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf" ^
  --spec-draft-ngl all ^
  --spec-draft-n-max 2 ^
  --spec-draft-p-min 0 ^
  -ngl all ^
  -c 24576 ^
  -np 1 ^
  -fa on ^
  --no-mmap ^
  -b 2048 ^
  -ub 512 ^
  --jinja ^
  --reasoning off ^
  --temp 0.7 ^
  --top-k 20 ^
  --top-p 0.8 ^
  --min-p 0 ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
