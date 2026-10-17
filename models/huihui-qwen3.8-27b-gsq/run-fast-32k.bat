@echo off
rem Qwen3.8-27B Huihui abliterated GSQ-RCO-IQ3_S (MTP) - FAST: 32k context, MTP 3 (53 tok/s) (kernel: llamacpp)
rem 52.5 tok/s (code 58.0 / chat 47.0), draft accepted 75%, 14.6 GB VRAM; image ok (vision on GPU runs out of memory on long prompts)
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\llamacpp"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\llama-server.exe" ( echo Kernel llamacpp missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\llama-server.exe" ^
  -m "%M%\Huihui-Qwen3.8-27B-abliterated-GSQ-RCO-IQ3_S-mtp.gguf" ^
  --mmproj "%M%\mmproj-F16.gguf" ^
  --no-mmproj-offload ^
  --spec-type draft-mtp ^
  --spec-draft-n-max 3 ^
  --spec-draft-p-min 0 ^
  -ngl all ^
  -c 32768 ^
  -np 1 ^
  -fa on ^
  --load-mode none ^
  -b 2048 ^
  -ub 512 ^
  --cache-ram 2048 ^
  --jinja ^
  --temp 0.7 ^
  --top-k 20 ^
  --top-p 0.8 ^
  --min-p 0 ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
