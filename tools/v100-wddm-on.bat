@echo off
rem Switches the Tesla V100 from TCC to WDDM so that WSL2 (Linux) can use it (needed for PXA on Linux).
rem Run as Administrator, then REBOOT. Undo with v100-tcc-back.bat.
rem Note: in WDDM mode Windows reserves a little VRAM and adds some driver overhead, so the tightest llama.cpp presets
rem (e.g. MiniCPM-V fast-224k) may no longer fit; Windows' 2-second GPU timeout (TDR) also applies to long kernels.
net session >nul 2>&1 || (echo Please right-click this file and choose "Run as administrator". & pause & exit /b 1)
nvidia-smi -i 0 -dm 0
if errorlevel 1 (
  echo.
  echo The driver refused WDDM mode for this card. PXA would then need a native Ubuntu install instead of WSL.
  pause
  exit /b 1
)
echo.
nvidia-smi --query-gpu=name,driver_model.current,driver_model.pending --format=csv
echo.
echo Done. "pending" should say WDDM. Restart Windows now to apply it.
pause
