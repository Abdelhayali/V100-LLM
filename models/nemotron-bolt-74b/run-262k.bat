@echo off
rem NVIDIA Nemotron-3.5-Bolt-74B-A9B (2-bit) - 262k context, vision on CPU (kernel: llamacpp)
rem ~20 tok/s gen, ~275 tok/s prompt; 250k-token prompt OK (231 tok/s prompt, 12.8 tok/s gen at 250k); image OK
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\llamacpp"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\llama-server.exe" ( echo Kernel llamacpp missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\llama-server.exe" ^
  -m "%M%\NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB.gguf" ^
  --mmproj "%M%\mmproj-NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB.gguf" ^
  --no-mmproj-offload ^
  -ngl 99 ^
  --n-cpu-moe 44 ^
  -t 14 ^
  --fit off ^
  --load-mode none ^
  -c 262144 ^
  -ctk q8_0 ^
  -ctv q8_0 ^
  -np 1 ^
  -fa on ^
  -b 2048 ^
  -ub 512 ^
  --jinja ^
  --temp 1.0 ^
  --top-p 0.95 ^
  --top-k 0 ^
  --min-p 0.0 ^
  --repeat-penalty 1.0 ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
