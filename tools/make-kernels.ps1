# Builds D:\V100-LLM\_kernels\<engine>\ : each engine's executables + every DLL it needs + licences.
$ErrorActionPreference = 'Stop'
$K   = 'D:\V100-LLM\_kernels'
$rel = 'D:\v100-llm-windows-release\v100-llm-windows'
$rt  = "$rel\bin\runtime"                     # CUDA 12.9 (cudart, cublas, cublasLt) + MSVC + OpenMP runtime
$lic = "$rel\LICENSES"
$exes = 'llama-server.exe', 'llama-cli.exe', 'llama-bench.exe'

function New-Kernel($name, $exeDir, $licFiles, [switch] $Runtime) {
    $d = Join-Path $K $name
    New-Item -ItemType Directory -Force "$d\LICENSES" | Out-Null
    foreach ($e in $exes) { if (Test-Path "$exeDir\$e") { Copy-Item "$exeDir\$e" $d -Force } }
    if ($Runtime) { Copy-Item "$rt\*.dll" $d -Force }
    foreach ($l in $licFiles) { Copy-Item $l "$d\LICENSES\" -Force }
    $mb = [math]::Round(((Get-ChildItem $d -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB)
    "kernel $name : $mb MB"
}

New-Kernel 'pxa'      "$rel\bin\pxa"     @("$lic\PXA-LICENSE.txt", "$lic\PXA-NOTICE.txt", "$lic\NVIDIA-CUDA-EULA.txt") -Runtime
New-Kernel 'fastmtp'  "$rel\bin\fastmtp" @("$lic\llama.cpp-LICENSE.txt", "$lic\NVIDIA-CUDA-EULA.txt") -Runtime
New-Kernel 'llamacpp' 'D:\nemotron-bolt\llama.cpp\build\bin' @('D:\nemotron-bolt\llama.cpp\LICENSE', "$lic\NVIDIA-CUDA-EULA.txt") -Runtime
Rename-Item "$K\llamacpp\LICENSES\LICENSE" 'llama.cpp-LICENSE.txt' -Force -EA SilentlyContinue

# Prism ML fork: the official Windows CUDA 12.4 release (it brings its own CUDA DLLs)
$p = "$K\prism"; New-Item -ItemType Directory -Force "$p\LICENSES" | Out-Null
Copy-Item 'D:\bonsai2-small-gpu\bin\prism-cuda12\*' $p -Recurse -Force
Set-Content "$p\LICENSES\SOURCE.txt" "Prism ML fork of llama.cpp (MIT), release prism-b10777-e3de715, files:`nhttps://github.com/PrismML-Eng/llama.cpp/releases/download/prism-b10777-e3de715/llama-prism-b10777-e3de715-bin-win-cuda-12.4-x64.zip`nhttps://github.com/PrismML-Eng/llama.cpp/releases/download/prism-b10777-e3de715/cudart-llama-bin-win-cuda-12.4-x64.zip"
"kernel prism : {0} MB" -f [math]::Round(((Get-ChildItem $p -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB)
