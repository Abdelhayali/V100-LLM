@echo off
rem Underdog Saluki 27B (Qwen3.8 2-bit, MTP) - 262k context, MTP, vision on CPU (kernel: llamacpp)
rem 36-52 tok/s gen (MTP); 252k-token prompt OK (149 tok/s prompt, 13 tok/s gen at 252k); image OK
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\llamacpp"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\llama-server.exe" ( echo Kernel llamacpp missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\llama-server.exe" ^
  -m "%M%\Underdog-Saluki-27B-1.0-IQ2-mix-MTP.gguf" ^
  --mmproj "%M%\mmproj-Underdog-Saluki-27B-1.0-Q8_0.gguf" ^
  --no-mmproj-offload ^
  --spec-type draft-mtp ^
  --spec-draft-n-max 3 ^
  --spec-draft-p-min 0 ^
  -ngl 99 ^
  -c 262144 ^
  -ctk q4_0 ^
  -ctv q4_0 ^
  -np 1 ^
  -fa on ^
  --load-mode none ^
  -b 2048 ^
  -ub 256 ^
  --jinja ^
  --temp 0.6 ^
  --top-p 0.95 ^
  --top-k 20 ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
