@echo off
rem Qwen3.8-27B Unsloth UD-IQ3_S (MTP) - FULL 262k context, KV streaming (6-12 tok/s) (kernel: kvstream)
rem decode at a filled context: 12.3 tok/s at 99k, 8.9 at 185k, 6.4 at 257k (q4_0 KV, 3500 MiB arena, PCIe 3.0); text only; use max-192k or long-96k-dflash when 192k is enough (faster)
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\kvstream"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\llama-server.exe" ( echo Kernel kvstream missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\llama-server.exe" ^
  -m "%M%\Qwen3.8-27B-UD-IQ3_S.gguf" ^
  --mmproj "%M%\mmproj-F16.gguf" ^
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
