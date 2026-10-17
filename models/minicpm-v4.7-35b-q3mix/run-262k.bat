@echo off
rem MiniCPM-V 4.7 35B-A3B Q3 mix (official mix_q3gud_im) - 262k context, vision on GPU (56 tok/s) (kernel: llamacpp)
rem 54.3 tok/s gen (n-cpu-moe 8); 250k needle passed: not tested
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\llamacpp"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\llama-server.exe" ( echo Kernel llamacpp missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\llama-server.exe" ^
  -m "%M%\MiniCPM-V-4_7-35B-A3B-mix_q3gud_im.gguf" ^
  --mmproj "%M%\mmproj-model-f16-4x.gguf" ^
  -ngl 99 ^
  --n-cpu-moe 8 ^
  -t 14 ^
  --fit off ^
  -c 262144 ^
  -ctk q4_0 ^
  -ctv q4_0 ^
  -np 1 ^
  -fa on ^
  --load-mode none ^
  -b 2048 ^
  -ub 512 ^
  --jinja ^
  --temp 0.7 ^
  --top-p 0.8 ^
  --top-k 20 ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
