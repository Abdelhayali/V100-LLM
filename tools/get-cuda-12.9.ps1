# Downloads the CUDA 12.9.1 toolkit pieces needed to build (nvcc, cudart, cuBLAS, CCCL, ...)
# from NVIDIA's official redistributable archives into build\cuda-12.9, verifying each SHA-256.
# No installer, no admin rights, no change to system PATH/CUDA_PATH (CUDA 13.x can stay installed).
# CUDA 12.x is required: CUDA 13 dropped Volta (sm_70).
$ErrorActionPreference = 'Stop'
$dest = Join-Path $PSScriptRoot 'cuda-12.9'
$base = 'https://developer.download.nvidia.com/compute/cuda/redist'
$manifest = Invoke-RestMethod "$base/redistrib_12.9.1.json"
$tmp = Join-Path $env:TEMP 'cuda129-redist'; New-Item -ItemType Directory -Force $tmp, $dest | Out-Null
foreach ($k in 'cuda_nvcc','cuda_cudart','cuda_cccl','libcublas','cuda_nvml_dev','cuda_nvtx','visual_studio_integration','cuda_nvprune') {
    $w = $manifest.$k.'windows-x86_64'
    $zip = Join-Path $tmp (Split-Path $w.relative_path -Leaf)
    Write-Host "Downloading $k ..."
    & curl.exe -fsSL --retry 10 -o $zip "$base/$($w.relative_path)"
    if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne $w.sha256.ToUpper()) { throw "Checksum mismatch: $k" }
    $x = Join-Path $tmp 'x'; if (Test-Path $x) { Remove-Item -Recurse -Force $x }
    Expand-Archive $zip -DestinationPath $x
    Get-ChildItem $x | ForEach-Object { Copy-Item -Recurse -Force "$($_.FullName)\*" $dest }
}
Remove-Item -Recurse -Force $tmp
& "$dest\bin\nvcc.exe" --version | Select-Object -Last 2
