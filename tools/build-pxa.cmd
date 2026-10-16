@echo off
rem Builds PXA (https://github.com/poisonxa16/pxa) for Windows + Tesla V100 (sm_70) with the Windows port patch.
rem Output: build\pxa\build\bin  (copy llama-*.exe to bin\pxa)
call "%~dp0_env.cmd" || exit /b 1
cd /d "%BUILDDIR%"
if not exist pxa ( git clone https://github.com/poisonxa16/pxa pxa || exit /b 1 )
cd pxa
set /p BASE=<"%BUILDDIR%..\patches\pxa-base-commit.txt"
git checkout -q %BASE% || exit /b 1
git apply --check "%BUILDDIR%..\patches\pxa-windows.patch" 2>nul && git apply "%BUILDDIR%..\patches\pxa-windows.patch"
cmake -B build -S . -G Ninja -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_CUDA_COMPILER=%CUDA_CMAKE%/bin/nvcc.exe -DCUDAToolkit_ROOT=%CUDA_CMAKE% ^
  -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=70 -DGGML_SCHED_MAX_COPIES=2 ^
  -DPXA_PXQN_CLOSED_SRC=OFF -DPXA_PXQ_ENCODER=OFF -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=OFF ^
  -DCMAKE_CUDA_FLAGS="-DWIN32_LEAN_AND_MEAN -DNOMINMAX -diag-suppress 221" || exit /b 1
cmake --build build --target llama-server llama-cli llama-bench || exit /b 1
echo BUILD OK: %CD%\build\bin
