@echo off
rem Qwen3.8-27B Unsloth UD-IQ3_S (MTP) - 192k context, no MTP, q4 KV (28 tok/s) (kernel: llamacpp)
rem 27.9 tok/s, 15.5 GB VRAM; image ok (262k does not fit)
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\llamacpp"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\llama-server.exe" ( echo Kernel llamacpp missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\llama-server.exe" ^
  -m "%M%\Qwen3.8-27B-UD-IQ3_S.gguf" ^
  --mmproj "%M%\mmproj-F16.gguf" ^
  --no-mmproj-offload ^
  -ngl all ^
  -c 196608 ^
  -ctk q4_0 ^
  -ctv q4_0 ^
  -np 1 ^
  -fa on ^
  --load-mode none ^
  -b 2048 ^
  -ub 256 ^
  --cache-ram 2048 ^
  --jinja ^
  --temp 0.7 ^
  --top-k 20 ^
  --top-p 0.8 ^
  --min-p 0 ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
