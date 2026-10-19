"""Unlimited-OCR worker: an image or a PDF -> markdown text.

    python ocr_worker.py --device cuda|cpu --input FILE --out RESULT.json [--pages 1-5] [--dpi 200]

Runs once per request and exits, so the GPU / RAM is free again afterwards. GPU: fp16 (the V100 has no bf16),
~7 GB VRAM. CPU: fp32, ~14 GB RAM. The result JSON is {"ok", "text", "pages", "seconds", "device", "error"}."""
import argparse, json, os, re, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = HERE / "model"
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
DET_RE = re.compile(r'<\|det\|>([^<\s]+)(?:\s*\[[^\]]*\])?\s*<\|/det\|>(.*)', re.DOTALL)
REF_RE = re.compile(r'<\|ref\|>.*?<\|/ref\|>', re.DOTALL)


def remove_det(raw: str) -> str:
    """Strips the <|det|>type [bbox]<|/det|> layout markers (the model card's post-processing)."""
    blocks, cur = [], None
    for line in REF_RE.sub("", raw).splitlines():
        line = line.rstrip()
        if not line:
            continue
        m = DET_RE.match(line)
        if m:
            category, content = m.group(1).strip(), m.group(2).strip()
            if cur is not None:
                blocks.append(cur)
            cur = [] if category == "image" else ([content] if content else [])
            continue
        if cur is None:
            cur = []
        cur.append(line)
    if cur is not None:
        blocks.append(cur)
    return "\n\n".join("\n".join(b) for b in blocks if b).strip()


def fuse_moe(model):
    """Faster decode for the DeepSeek-V2 MoE layers. The original moe_infer loops over the experts in Python and syncs
    with the CPU in every layer for every token; here the expert weights are stacked once (the expert modules then use
    views of the stack, so no extra memory) and a few tokens are computed with one gather + batched matmul."""
    import torch
    n = 0
    for mod in model.modules():
        if type(mod).__name__ != "DeepseekV2MoE" or not hasattr(mod, "experts"):
            continue
        ex = mod.experts
        for name in ("gate_proj", "up_proj", "down_proj"):
            st = torch.stack([getattr(e, name).weight.data for e in ex])        # [E, out, in]
            for i, e in enumerate(ex):
                getattr(e, name).weight.data = st[i]
            setattr(mod, "_w_" + name, st)
        act, orig = ex[0].act_fn, mod.moe_infer

        def fast(x, topk_ids, topk_weight, mod=mod, act=act, orig=orig):
            if x.shape[0] > 8:                                                 # prefill: original path
                return orig(x, topk_ids, topk_weight)
            g = torch.einsum("tkih,th->tki", mod._w_gate_proj[topk_ids], x)
            u = torch.einsum("tkih,th->tki", mod._w_up_proj[topk_ids], x)
            y = torch.einsum("tkhi,tki->tkh", mod._w_down_proj[topk_ids], act(g) * u)
            return (y * topk_weight.unsqueeze(-1).to(y.dtype)).sum(1).to(x.dtype)
        mod.moe_infer = fast
        n += 1
    return n


def page_range(spec, n):
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        lo = max(1, int(a)); hi = min(n, int(b) if b else lo)
        out += list(range(lo - 1, hi))
    return sorted(set(out))


def pdf_to_images(pdf, spec, dpi, tmp):
    import fitz
    doc = fitz.open(pdf)
    idx = page_range(spec, len(doc))
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    paths = []
    for i in idx:
        out = os.path.join(tmp, f"page_{i + 1:04d}.png")
        doc[i].get_pixmap(matrix=mat).save(out)
        paths.append(out)
    doc.close()
    return paths, [i + 1 for i in idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pages", default="")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=8192, help="prompt + output tokens per page")
    ap.add_argument("--multi", action="store_true", help="read all pages in one pass instead of page by page")
    a = ap.parse_args()

    os.environ["OCR_DEVICE"] = a.device
    os.environ["OCR_DTYPE"] = "float16" if a.device == "cuda" else "float32"
    t0 = time.time()
    res = {"ok": False, "text": "", "pages": [], "device": a.device, "error": ""}
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
        if a.device == "cpu":
            torch.set_num_threads(a.threads or max(1, (os.cpu_count() or 4) // 2))
        elif not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available")
        src = Path(a.input)
        if not src.is_file():
            raise FileNotFoundError(str(src))
        tmp = tempfile.mkdtemp(prefix="uocr_")
        if src.suffix.lower() == ".pdf":
            images, pages = pdf_to_images(str(src), a.pages, a.dpi, tmp)
            if len(images) > a.max_pages:
                images, pages = images[:a.max_pages], pages[:a.max_pages]
                res["error"] = f"only the first {a.max_pages} pages were read"
        elif src.suffix.lower() in IMG_EXT:
            images, pages = [str(src)], [1]
        else:
            raise ValueError("not an image or a PDF: " + src.suffix)
        if not images:
            raise ValueError("no pages to read")

        dtype = torch.float16 if a.device == "cuda" else torch.float32
        tok = AutoTokenizer.from_pretrained(str(MODEL), trust_remote_code=True)
        model = AutoModel.from_pretrained(str(MODEL), trust_remote_code=True, use_safetensors=True,
                                          torch_dtype=dtype, attn_implementation="eager")
        model = model.eval().to(a.device)
        if not os.environ.get("OCR_NO_FUSE"):
            fuse_moe(model)
        res["load_seconds"] = round(time.time() - t0, 1)

        # cap the output: a real page is a few thousand tokens; a model stuck in a loop otherwise runs to 32k tokens
        # and its eager attention keeps growing in VRAM (a phone screenshot reached 13 GB)
        common = dict(max_length=a.max_tokens, no_repeat_ngram_size=35, temperature=0.0)
        if not a.multi:   # page by page (single-image "gundam" mode: global view + 640 crops; faster and sharper)
            texts = []
            for i, img in enumerate(images):
                raw = model.infer(tok, prompt="<image>document parsing.", image_file=img, output_path=tmp,
                                  base_size=1024, image_size=640, crop_mode=True, eval_mode=True, ngram_window=128,
                                  **common)
                texts.append(remove_det(raw))
                print(f"page {pages[i]} done at {time.time() - t0:.0f} s", file=sys.stderr, flush=True)
        else:             # all pages in one pass (the model's long-horizon mode)
            raw, _ = model.infer_multi(tok, prompt="<image>Multi page parsing.", image_files=images,
                                       output_path=tmp, image_size=1024, ngram_window=1024, **common)
            parts = raw.split("<PAGE>")
            parts = [p for p in parts[1:]] if len(parts) > 1 else parts
            texts = [remove_det(p) for p in parts]
        res["pages"] = [{"page": pages[i] if i < len(pages) else i + 1, "text": t} for i, t in enumerate(texts)]
        res["text"] = "\n\n".join(
            (f"## Page {p['page']}\n\n" if len(texts) > 1 else "") + p["text"] for p in res["pages"]).strip()
        res["ok"] = True
    except Exception as e:  # reported to the bridge, which shows it to the model
        res["error"] = f"{type(e).__name__}: {e}"
    res["seconds"] = round(time.time() - t0, 1)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print("OCR done" if res["ok"] else "OCR failed: " + res["error"], file=sys.stderr)
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
