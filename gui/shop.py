"""Model shop: find GGUF models on Hugging Face and install them next to the curated catalog.

Installed models go to user-models.json (merged into the catalog by launcher.catalog(), not in git) and download
through the launcher's own downloader: model files only (.gguf), checked against the SHA-256 Hugging Face lists for
each file. They run on the standard llama.cpp engine with --fit, which keeps as much of the model on the V100 as fits
and the rest in system RAM. Gated repos use the user's own Hugging Face login (launcher.hf_token()).
"""
import json
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

VRAM_GB = 16.0
SHOP_PREFIX = "shop-"
DRAFTER = re.compile(r"(dflash|dspark|eagle|[-_]mtp[-_.]|draft)", re.I)
SPLIT = re.compile(r"-(\d{5})-of-(\d{5})\.gguf$", re.I)
QUANT = re.compile(r"(IQ\d_[A-Z]+|Q\d_K(?:_[SMLX]{1,2})?|Q\d_\d|Q\d_K_XL|UD-[A-Z0-9_]+|MXFP4|BF16|F16|F32)", re.I)


def _get(url: str, token: str = ""):
    hdr = {"User-Agent": "V100-LLM"}
    if token:
        hdr["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=30) as r:
        return json.loads(r.read())


def search(q: str, token: str = "") -> list[dict]:
    qs = urllib.parse.urlencode({"search": q, "filter": "gguf", "sort": "downloads", "direction": "-1", "limit": "30",
                                 "full": "false"})
    out = []
    for m in _get("https://huggingface.co/api/models?" + qs, token):
        tags = m.get("tags") or []
        out.append({"repo": m["id"], "downloads": m.get("downloads", 0), "likes": m.get("likes", 0),
                    "gated": bool(m.get("gated")), "updated": m.get("lastModified", ""),
                    "license": next((t.split(":", 1)[1] for t in tags if t.startswith("license:")), ""),
                    "pipeline": m.get("pipeline_tag", "")})
    return out


def fit(size_gb: float) -> tuple[str, str]:
    """Rough fit on a 16 GB V100 with a 32k context (KV + compute buffers ~1.5-2.5 GB)."""
    if size_gb <= VRAM_GB - 2.5:
        return "gpu", "fits on the GPU with a 32k context"
    if size_gb <= VRAM_GB - 1.0:
        return "tight", "fits on the GPU with a short context (8k); 32k spills a little to the CPU"
    if size_gb <= 60:
        return "offload", "too big for 16 GB alone: part runs on the CPU (needs system RAM, slower)"
    return "too_big", "very large: needs a lot of system RAM and will be slow"


def files(repo: str, token: str = "") -> dict:
    """The GGUF choices of a repo: split files grouped into one choice, mmproj (vision) files listed apart."""
    info = _get(f"https://huggingface.co/api/models/{repo}", token)
    tree = _get(f"https://huggingface.co/api/models/{repo}/tree/main?recursive=true", token)
    choices, mmproj = {}, []
    for f in tree:
        p = f.get("path", "")
        if f.get("type") != "file" or not p.lower().endswith(".gguf"):
            continue
        lfs = f.get("lfs") or {}
        item = {"name": p, "size": lfs.get("size") or f.get("size") or 0, "sha256": lfs.get("oid") or ""}
        if "mmproj" in p.lower():
            mmproj.append(item)
            continue
        if DRAFTER.search(Path(p).name) or item["size"] < 2e9 and "draft" in p.lower():
            continue          # speculative-decoding drafters (DFlash / MTP / EAGLE) are not models on their own
        key = SPLIT.sub(".gguf", p)
        choices.setdefault(key, []).append(item)
    out = []
    for key, parts in choices.items():
        parts.sort(key=lambda x: x["name"])
        size = sum(x["size"] for x in parts)
        q = QUANT.search(Path(key).name)
        kind, why = fit(size / 1e9)
        out.append({"key": key, "quant": q.group(1).upper() if q else "", "size": size, "parts": parts,
                    "fit": kind, "fit_text": why})
    out.sort(key=lambda c: c["size"])
    return {"repo": repo, "gated": bool(info.get("gated")), "license": (info.get("cardData") or {}).get("license", ""),
            "choices": out, "mmproj": sorted(mmproj, key=lambda x: x["size"])}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def entry(repo: str, choice: dict, mmproj: dict | None) -> dict:
    """A catalog entry for one chosen file (+ optional vision projector)."""
    base = Path(choice["key"]).name[:-5]
    mid = SHOP_PREFIX + _slug(repo.split("/")[-1] + "-" + (choice["quant"] or base))
    url = lambda name: f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(name)}"
    fl = [{"name": Path(x["name"]).name, "repo": repo, "sha256": x["sha256"], "size": x["size"], "url": url(x["name"])}
          for x in choice["parts"]]
    if mmproj:
        fl.append({"name": Path(mmproj["name"]).name, "repo": repo, "sha256": mmproj["sha256"], "size": mmproj["size"],
                   "url": url(mmproj["name"])})
    common = [["-fa", "on", ""], ["-np", "1", ""], ["--jinja", "", ""], ["--fit", "on", "keep what fits on the GPU, rest on the CPU"],
              ["--cache-ram", "2048", "prompt cache in RAM, MiB"]]
    if mmproj:
        common.insert(0, ["--no-mmproj-offload", "", "vision encoder on CPU"])
    size_gb = choice["size"] / 1e9
    presets = [{"id": "auto-32k", "name": "32k context, auto fit (shop default)", "kernel": "llamacpp", "kernels": ["llamacpp"],
                "bench": "", "params": common + [["-c", "32768", "context"]]},
               {"id": "auto-8k", "name": "8k context, auto fit (more on the GPU)", "kernel": "llamacpp", "kernels": ["llamacpp"],
                "bench": "", "params": common + [["-c", "8192", "context"]]}]
    if size_gb > VRAM_GB - 2.5:
        presets.reverse()      # big model: the short context first
    return {"id": mid, "name": f"{repo.split('/')[-1]} {choice['quant']}".strip() + " (shop)",
            "desc": f"Installed from the Model shop: {repo}, {Path(choice['key']).name} ({size_gb:.1f} GB). "
                    "Standard llama.cpp with --fit; not tuned like the catalog models.",
            "source": {"repo": repo, "shop": True}, "files": fl, "model": fl[0]["name"],
            **({"mmproj": fl[-1]["name"]} if mmproj else {}), "presets": presets}


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"models": []}


def add(path: Path, e: dict):
    d = load(path)
    d["models"] = [m for m in d["models"] if m["id"] != e["id"]] + [e]
    path.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")


def remove(path: Path, models_dir: Path, mid: str) -> bool:
    if not mid.startswith(SHOP_PREFIX):
        raise ValueError("only models installed from the shop can be removed here")
    d = load(path)
    keep = [m for m in d["models"] if m["id"] != mid]
    found = len(keep) != len(d["models"])
    d["models"] = keep
    path.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    folder = models_dir / mid
    if folder.is_dir() and folder.resolve().parent == models_dir.resolve():
        shutil.rmtree(folder, ignore_errors=True)
    return found
