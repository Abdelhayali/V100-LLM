"""Download the image generator: Qwen-Image-2512 (GGUF) + its text encoder, VAE and the 8-step Lightning LoRA, and
the stable-diffusion.cpp Windows CUDA 12 build that runs them (CUDA 12: the V100 / sm_70 is not supported by CUDA 13).

    python get-image-model.py [--dest C:\\LocalAI-Bridge-OCR\\qwen-image] [--quant Q3_K_M]

Files land in <dest>; ocr\\image is linked to it. Downloads resume if they are interrupted.
"""
import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SD_TAG = "master-929-3f8527a"
SD_BASE = f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{SD_TAG}/"
HF = "https://huggingface.co/{repo}/resolve/main/{path}"


def files(quant):
    return [
        (HF.format(repo="unsloth/Qwen-Image-2512-GGUF", path=f"qwen-image-2512-{quant}.gguf"), f"qwen-image-2512-{quant}.gguf"),
        (HF.format(repo="unsloth/Qwen2.5-VL-7B-Instruct-GGUF", path="Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf"), "Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf"),
        (HF.format(repo="Comfy-Org/Qwen-Image_ComfyUI", path="split_files/vae/qwen_image_vae.safetensors"), "qwen_image_vae.safetensors"),
        (HF.format(repo="lightx2v/Qwen-Image-2512-Lightning", path="Qwen-Image-2512-Lightning-8steps-V1.0-bf16.safetensors"),
         "lora/Qwen-Image-2512-Lightning-8steps-V1.0-bf16.safetensors"),
        (SD_BASE + "sd-master-3f8527a-bin-win-cuda12-x64.zip", "_zips/sd-cuda12.zip"),
        (SD_BASE + "cudart-sd-bin-win-cu12-x64.zip", "_zips/cudart.zip"),
    ]


def get(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"\n== {dest.name}", flush=True)
    for attempt in range(8):
        r = subprocess.run(["curl.exe", "-fL", "--retry", "10", "--retry-delay", "5", "-C", "-", "-o", str(dest), url])
        if r.returncode in (0, 33):       # 33: the server does not resume a complete file = already done
            return
        print(f"   curl exit {r.returncode}, retrying", flush=True)
    raise SystemExit(f"download failed: {url}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=r"C:\LocalAI-Bridge-OCR\qwen-image")
    ap.add_argument("--quant", default="Q3_K_M")
    a = ap.parse_args()
    dest = Path(a.dest)
    for url, name in files(a.quant):
        get(url, dest / name)
    bindir = dest / "sd"
    bindir.mkdir(exist_ok=True)
    for z in ("_zips/sd-cuda12.zip", "_zips/cudart.zip"):
        with zipfile.ZipFile(dest / z) as f:
            f.extractall(bindir)
    exe = next(bindir.rglob("sd-cli.exe"), None) or next(bindir.rglob("sd.exe"), None)
    print("\nprogram:", exe)
    link = HERE / "image"
    if not link.exists():
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(dest)], check=False)
    print("done:", dest)


if __name__ == "__main__":
    sys.exit(main())
