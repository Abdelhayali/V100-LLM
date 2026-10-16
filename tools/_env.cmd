@echo off
rem Build environment: MSVC x64 + local CUDA 12.9 (from get-cuda-12.9.ps1).
set "BUILDDIR=%~dp0"
set "CUDA_DIR=%BUILDDIR%cuda-12.9"
if not exist "%CUDA_DIR%\bin\nvcc.exe" ( echo Run: powershell -ExecutionPolicy Bypass -File build\get-cuda-12.9.ps1 & exit /b 1 )
for /f "usebackq delims=" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -property installationPath`) do set "VSDIR=%%i"
if not defined VSDIR ( echo Install Visual Studio 2022 Build Tools with the C++ workload. & exit /b 1 )
call "%VSDIR%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set "CUDA_PATH=%CUDA_DIR%"
set "CUDAToolkit_ROOT=%CUDA_DIR%"
set "PATH=%CUDA_DIR%\bin;%VSDIR%\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%"
set "CUDA_CMAKE=%CUDA_DIR:\=/%"
