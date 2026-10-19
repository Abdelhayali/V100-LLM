"""Fills sha256 + size for every model file from the Hugging Face API and writes D:/V100-LLM/catalog.json."""
import json
import urllib.request
from pathlib import Path

src = json.loads(Path(__file__).with_name("catalog-src.json").read_text(encoding="utf-8"))
trees = {}


def _hf_auth():
    import os
    tok = os.environ.get("HF_TOKEN", "")
    for f in (Path(__file__).resolve().parent.parent / "hf-token.txt", Path.home() / ".cache" / "huggingface" / "token"):
        if not tok and f.exists():
            tok = f.read_text(encoding="utf-8").strip()
    return {"Authorization": "Bearer " + tok} if tok else {}


HF_AUTH = _hf_auth()


def tree(repo):
    if repo not in trees:
        with urllib.request.urlopen(urllib.request.Request(f"https://huggingface.co/api/models/{repo}/tree/main?recursive=true",
                headers=HF_AUTH), timeout=120) as r:   # gated repos hide the SHA-256 from anonymous requests
            trees[repo] = {f["path"]: f for f in json.loads(r.read())}
    return trees[repo]


for m in src["models"]:
    if m["files"] and isinstance(m["files"][0], dict):   # already resolved (setup-managed models like Strata)
        continue
    files = []
    for repo, name in m["files"]:
        f = tree(repo)[name]
        files.append({"name": name, "repo": repo, "sha256": f["lfs"]["oid"], "size": f["lfs"]["size"],
                      "url": f"https://huggingface.co/{repo}/resolve/main/{name}"})
    m["files"] = files
    print(f"{m['id']:22} {sum(x['size'] for x in files) / 1e9:6.1f} GB  {len(files)} files")
out = Path(__file__).resolve().parent.parent / "catalog.json"
out.write_text(json.dumps(src, indent=1), encoding="utf-8")
print("wrote", out)
