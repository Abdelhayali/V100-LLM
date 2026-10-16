@echo off
rem Ternary-Bonsai-2-27B Uncensored Heretic - 262k context, vision on GPU (PQ2_0) (kernel: prism)
rem 47-50 tok/s gen, 13.2 GB VRAM; 252k-token prompt OK (148 tok/s prompt, 6 tok/s gen at 252k); image on GPU 2.3 s
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\prism"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\llama-server.exe" ( echo Kernel prism missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\llama-server.exe" ^
  -m "%M%\Ternary-Bonsai-2-27B-Uncensored-Heretic-PQ2_0.gguf" ^
  --mmproj "%M%\mmproj-Q8_0.gguf" ^
  -ngl 99 ^
  -c 262144 ^
  -ctk q4_0 ^
  -ctv q4_0 ^
  -np 1 ^
  -fa on ^
  --no-mmap ^
  -b 2048 ^
  -ub 256 ^
  --jinja ^
  --temp 1.0 ^
  --top-p 0.95 ^
  --top-k 20 ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
