@echo off
rem OrcaCyber-Nano-1.0 27B Mix-13G (MTP built in) - FULL 262k context, KV streaming (text only) (kernel: kvstream)
rem 23.8 tok/s code after a 19.6k-token prompt (KV cache in system RAM, streamed over PCIe; slower as the context fills, like Unsloth: ~6-12 tok/s at 100k-257k); text only
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\kvstream"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\llama-server.exe" ( echo Kernel kvstream missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\llama-server.exe" ^
  -m "%M%\OrcaCyber-Nano-1.0-AI-Defense-Mix-13G.gguf" ^
  --mmproj "%M%\mmproj-OrcaCyber-Nano-1.0-AI-Defense-F16.gguf" ^
  --no-mmproj ^
  --spec-type none ^
  -ngl 999 ^
  -c 262144 ^
  --shared-device-memory-mib 3500 ^
  -ctk q4_0 ^
  -ctv q4_0 ^
  -np 1 ^
  -fa on ^
  --fit off ^
  -b 256 ^
  -ub 256 ^
  --jinja ^
  --temp 0.7 ^
  --top-k 20 ^
  --top-p 0.8 ^
  --min-p 0 ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
