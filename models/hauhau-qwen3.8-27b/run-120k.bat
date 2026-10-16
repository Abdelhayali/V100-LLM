@echo off
rem Qwen3.8-27B HauhauCS Aggressive IQ3_XS - 120k context, vision on CPU (kernel: fastmtp)
rem ~46 tok/s short, ~14 tok/s at 118k (tested)
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
  --no-mmproj-offload ^
  --spec-type draft-mtp ^
  --spec-draft-n-max 2 ^
  --spec-draft-p-min 0 ^
  --spec-draft-type-k q4_0 ^
  --spec-draft-type-v q4_0 ^
  -ngl all ^
  -c 122880 ^
  -ctk q4_0 ^
  -ctv q4_0 ^
  -np 1 ^
  -fa on ^
  --no-mmap ^
  -b 2048 ^
  -ub 256 ^
  --jinja ^
  --reasoning off ^
  --temp 0.7 ^
  --top-k 20 ^
  --top-p 0.8 ^
  --min-p 0 ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
