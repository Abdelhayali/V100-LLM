@echo off
rem Builds llama.cpp at the commit HauhauCS FastMTP needs, with the FastMTP patch, for Tesla V100 (sm_70).
rem Output: build\llama.cpp\build\bin  (copy llama-*.exe to bin\fastmtp)
call "%~dp0_env.cmd" || exit /b 1
cd /d "%BUILDDIR%"
if not exist llama.cpp ( git clone https://github.com/ggml-org/llama.cpp llama.cpp || exit /b 1 )
cd llama.cpp
set /p BASE=<"%BUILDDIR%..\patches\llamacpp-base-commit.txt"
git checkout -q %BASE% || exit /b 1
git apply --check "%BUILDDIR%..\patches\HauhauCS-FastMTP-llama.cpp.patch" 2>nul && git apply "%BUILDDIR%..\patches\HauhauCS-FastMTP-llama.cpp.patch"
cmake -B build -S . -G Ninja -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_CUDA_COMPILER=%CUDA_CMAKE%/bin/nvcc.exe -DCUDAToolkit_ROOT=%CUDA_CMAKE% ^
  -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=70 -DGGML_NATIVE=OFF -DGGML_AVX2=ON ^
  -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=OFF -DLLAMA_BUILD_TESTS=OFF || exit /b 1
cmake --build build --target llama-server llama-cli llama-bench || exit /b 1
echo BUILD OK: %CD%\build\bin
