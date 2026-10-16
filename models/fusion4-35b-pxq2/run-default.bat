@echo off
rem PXA-Fusion4-35B-A3B PXQ2 - 16k context, vision on GPU (kernel: pxa)
rem 64-76 tok/s gen, 2014 tok/s prompt
rem Open http://127.0.0.1:%PORT% (default 8899). Extra arguments are passed to llama-server.
if not defined PORT set "PORT=8899"
if not defined HOST set "HOST=127.0.0.1"
set "K=%~dp0kernel\pxa"
set "M=%~dp0model"
set "PATH=%K%;%PATH%"
if not exist "%K%\llama-server.exe" ( echo Kernel pxa missing: open START-GUI.bat and press Download. & pause & exit /b 1 )
"%K%\llama-server.exe" ^
  -m "%M%\PXA-Fusion4-35B-PXQ2.gguf" ^
  --mmproj "%M%\mmproj-fusion2-f16.gguf" ^
  -ngl 99 ^
  -c 16384 ^
  -np 1 ^
  -fa on ^
  --jinja ^
  --reasoning off ^
  --presence-penalty 1.5 ^
  --repeat-penalty 1.15 ^
  --repeat-last-n 256 ^
  --dry-multiplier 0.8 ^
  --host %HOST% --port %PORT% %*
if errorlevel 1 pause
