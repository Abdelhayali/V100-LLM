# Moves model files into D:\V100-LLM\models\<id>\model and hard-links each model's engines into
# models\<id>\kernel\<engine> (hard links: full files on disk, no extra space). Safe to re-run.
param([string] $OnlyList = "")
$Only = @($OnlyList -split "," | Where-Object { $_ })
$ErrorActionPreference = 'Stop'
$R = 'D:\V100-LLM'
$layout = [ordered]@{
    'fusion4-35b-pxq2'      = @{ kernels = 'pxa'; files = 'D:\pxa\models\PXA-Fusion4-35B-PXQ2.gguf', 'D:\pxa\models\mmproj\mmproj-fusion2-f16.gguf' }
    'ornith-35b-pxq2'       = @{ kernels = 'pxa'; files = 'D:\pxa\models\Ornith-1.5-35B-A3B-PXQ2-GGUF.gguf', 'D:\pxa\models\mmproj\mmproj-Ornith-1.5-35B-BF16.gguf' }
    'qwen3.8-27b-pxq3'      = @{ kernels = 'pxa'; files = 'D:\pxa\models\Qwen3.8-27B-PXQ3-GGUF.gguf', 'D:\pxa\models\mmproj\mmproj-Qwen3.8-27B-Q8_0.gguf' }
    'hauhau-qwen3.8-27b'    = @{ kernels = 'fastmtp', 'llamacpp'; files = 'D:\qwen38-fastmtp\models\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ3_XS.gguf', 'D:\qwen38-fastmtp\models\Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf', 'D:\qwen38-fastmtp\models\mmproj-Qwen3.8-27B-Q8_0.gguf' }
    'nemotron-bolt-74b'     = @{ kernels = 'llamacpp'; files = 'D:\nemotron-bolt\models\NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB.gguf', 'D:\nemotron-bolt\models\mmproj-NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB.gguf' }
    'saluki-27b'            = @{ kernels = 'llamacpp'; files = 'D:\saluki-27b\models\Underdog-Saluki-27B-1.0-IQ2-mix-MTP.gguf', 'D:\saluki-27b\models\Underdog-Saluki-27B-1.0-IQ2-mix.gguf', 'D:\saluki-27b\models\mmproj-Underdog-Saluki-27B-1.0-Q8_0.gguf' }
    'bonsai-heretic-27b'    = @{ kernels = 'prism'; files = 'D:\bonsai-heretic-27b\models\Ternary-Bonsai-2-27B-Uncensored-Heretic-PTQ1_0.gguf', 'D:\bonsai-heretic-27b\models\Ternary-Bonsai-2-27B-Uncensored-Heretic-PQ2_0.gguf', 'D:\bonsai-heretic-27b\models\mmproj-Q8_0.gguf' }
    'minicpm-v4.7-35b'      = @{ kernels = 'llamacpp'; files = 'D:\minicpm-v47\models\MiniCPM-V-4_7-35B-A3B-IQ3_XS.gguf', 'D:\minicpm-v47\models\mmproj-model-f16-4x.gguf' }
}
foreach ($id in $layout.Keys) {
    if ($Only -and $Only -notcontains $id) { continue }
    $mdir = "$R\models\$id\model"; New-Item -ItemType Directory -Force $mdir | Out-Null
    foreach ($f in $layout[$id].files) {
        $dest = Join-Path $mdir (Split-Path $f -Leaf)
        if (Test-Path $dest) { continue }
        if (-not (Test-Path $f)) { Write-Output "  missing (GUI can download): $f"; continue }
        # a file used by several models (shared mmproj) is hard-linked from where it already moved to
        $already = Get-ChildItem "$R\models\*\model\$(Split-Path $f -Leaf)" -EA SilentlyContinue | Select-Object -First 1
        if ($already) { New-Item -ItemType HardLink -Path $dest -Target $already.FullName | Out-Null }
        else { Move-Item $f $dest }
    }
    foreach ($k in @($layout[$id].kernels)) {
        $src = "$R\_kernels\$k"; $kd = "$R\models\$id\kernel\$k"
        Get-ChildItem $src -Recurse -File | ForEach-Object {
            $t = Join-Path $kd $_.FullName.Substring($src.Length + 1)
            if (-not (Test-Path $t)) { New-Item -ItemType Directory -Force (Split-Path $t) | Out-Null; New-Item -ItemType HardLink -Path $t -Target $_.FullName | Out-Null }
        }
    }
    $gb = [math]::Round(((Get-ChildItem $mdir -File | Measure-Object Length -Sum).Sum) / 1GB, 1)
    "{0,-22} model {1,5} GB   kernels: {2}" -f $id, $gb, (@($layout[$id].kernels) -join ', ')
}
