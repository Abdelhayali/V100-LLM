@echo off
rem V100-LLM: starts the model launcher GUI at http://127.0.0.1:7860 (opens your browser).
rem First run: downloads the portable Python runtime (37 MB) from the GitHub release.
cd /d "%~dp0"
set "PY=%~dp0runtime\python\python.exe"
if not exist "%PY%" (
  echo Downloading the portable Python runtime ...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol='Tls12'; $z=Join-Path $env:TEMP 'v100llm-runtime.zip'; Invoke-WebRequest -UseBasicParsing 'https://github.com/Abdelhayali/V100-LLM/releases/download/kernels-v1/runtime.zip' -OutFile $z; Expand-Archive $z -DestinationPath '%~dp0.' -Force; Remove-Item $z"
)
if not exist "%PY%" ( echo Could not get the runtime. Download runtime.zip from the GitHub release and extract it here. & pause & exit /b 1 )
"%PY%" "%~dp0gui\launcher.py" %*
if errorlevel 1 pause
