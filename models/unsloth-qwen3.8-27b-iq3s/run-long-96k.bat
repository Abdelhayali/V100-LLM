@echo off
rem Qwen3.8-27B Unsloth UD-IQ3_S (MTP) - 96k context, MTP 4, q4 KV (51 tok/s) (kernel: llamacpp)
rem 50.6 tok/s (code 60.1 / chat 41.1), draft accepted 62%, 15.6 GB VRAM; image ok
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
  --spec-type draft-mtp ^
  --spec-draft-model "%M%\MTP/mtp-Qwen3.8-27B-Q4_0.gguf" ^
  --spec-draft-ngl all ^
  --spec-draft-n-max 4 ^
  --spec-draft-p-min 0 ^
  --spec-draft-type-k q4_0 ^
  --spec-draft-type-v q4_0 ^
  -ngl all ^
  -c 98304 ^
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
