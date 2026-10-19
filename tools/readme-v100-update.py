"""README: V100 kernel patch, adaptive KV streaming (full 262k), Unsloth speeds, Q3_K_XL row, thinking setting."""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "README.md"
t = p.read_text(encoding="utf-8")

reps = [
    ("| **Qwen3.8-27B Unsloth UD-IQ3_S** + MTP draft (official) | llama.cpp | 12.0 GB (+1.4 GB MTP) | 32k / 96k / 192k | **53 tok/s** at 32k, 51 at 96k, 28 at 192k (no MTP) | not run yet | CPU | ~2 GB | official 27B, fast MTP |",
     "| **Qwen3.8-27B Unsloth UD-IQ3_S** + MTP / DFlash2 (official) | llama.cpp (V100 patch) / kvstream | 12.0 GB (+1.1-1.4 GB drafter) | 32k / 96k / 192k / **262k** | **55 tok/s** at 32k (MTP), **58** at 96k (DFlash2, code ~73), 31 at 192k; full 262k: 12 / 9 / 6 tok/s at a filled 99k / 185k / 257k | 257k ✓ (streaming) | CPU | ~2 GB (+ KV in RAM for 262k) | official 27B, fast MTP, **full context** |\n"
     "| Qwen3.8-27B Unsloth UD-Q3_K_XL + DFlash2 (official) | llama.cpp | 13.2 GB (+1.1 GB drafter) | 32k | 55 tok/s (DFlash2, code ~70) | not run yet | CPU | ~2 GB | same speed as IQ3_S, lower score (76.9) |"),
    ("| `llamacpp` | upstream [llama.cpp](https://github.com/ggml-org/llama.cpp) (Nemotron-H, MiniCPM-V 4.7, draft-mtp) | `f336359`, CUDA 12.9, sm_70 |",
     "| `llamacpp` | upstream [llama.cpp](https://github.com/ggml-org/llama.cpp) (Nemotron-H, MiniCPM-V 4.7, draft-mtp, DFlash2) with the **V100 decode patch** (see below) | `f336359` + [`patches/llamacpp-f336359-v100-mmvq.patch`](patches/llamacpp-f336359-v100-mmvq.patch), CUDA 12.9, sm_70 |\n"
     "| `kvstream` | [llama.cpp adaptive KV streaming](https://github.com/RaymondHuang210129/llama.cpp-adaptive-kv-streaming): KV cache in system RAM, streamed through a VRAM arena, so Qwen3.8-27B runs the **full 262k context** on 16 GB | `db8fd5d`, CUDA 12.9, sm_70, FA pairs f16/q8_0-q4_0/q4_0-q4_0/q8_0-q8_0 |"),
    ("| 🔑 **OpenAI API anywhere** |",
     "| 🧠 **Thinking effort** | Off / Low / Medium / High / Max per chat (a llama.cpp thinking budget: 1k / 4k / 16k tokens / unlimited), so a reply never spends all its tokens thinking |\n| 🔑 **OpenAI API anywhere** |"),
]
for a, b in reps:
    assert a in t, a[:70]
    t = t.replace(a, b, 1)

section = """## V100 tuning notes

**Decode kernel patch** ([`patches/llamacpp-f336359-v100-mmvq.patch`](patches/llamacpp-f336359-v100-mmvq.patch), built into
the `llamacpp` kernel). On a V100 the 3-bit and 2-bit i-quant GEMV kernels were limited by their codebook lookups (30-40% of
the 900 GB/s), not by memory. The patch, active only on sm_70 and only for dense matrices (MoE experts keep the stock code):

- stages the IQ3_S / IQ3_XXS / IQ2_S / IQ2_XS / IQ2_XXS codebooks in shared memory (also for the fused gate projection);
- uses 4 rows per block for these types, Q3_K and IQ4_XS;
- decodes each weight block once for all 2-8 tokens of a speculative-decoding verify step (bit-identical results);
- runs ffn gate and up as two tuned launches instead of the fused kernel, which needs too many registers on Volta.

| Qwen3.8-27B UD-IQ3_S, one V100-SXM2-16GB | stock llama.cpp | patched |
|---|---|---|
| decode, no speculation | 30.6 tok/s | **33.7 tok/s** (+10%) |
| verify 4 / 8 tokens | 81 / 121 tok/s | 87 / 129 tok/s |
| IQ3_S GEMV 17408 x 5120 | 107 us (357 GB/s) | 81 us (471 GB/s) |

`test-backend-ops`: 16,562 tests OK, 0 failures (MUL_MAT, MUL_MAT_ID and the other ops). Dense Qwen3.8-27B quants gain about
8-12%, models whose weights are mostly MoE experts (MiniCPM-V, Nemotron) are unchanged.

**Full 262k context with KV streaming** (`kvstream` kernel, preset `full-262k-stream`). Decode with a really filled
context, q4_0 K/V, 3,500 MiB arena: 12.3 tok/s at 99k, 8.9 at 185k, 6.4 at 257k, with correct recall at every depth. Plain
llama.cpp is ~10% faster up to 192k (14.1 / 9.7 tok/s at 99k / 185k) but cannot start the model at 262k. q4_0 K is 2.3x
faster than q8_0 K at 257k because less KV crosses PCIe 3.0 every token.

**Clocks.** Under load this card runs at ~1,140 MHz (max 1,530) because of its 200 W power limit and ~82 C thermal
slowdown (`nvidia-smi` throttle reasons 0x4 and 0x20). The 3-bit kernels are compute-bound, so better cooling and a higher
power limit (if the adapter allows it) speed up every model.

"""
anchor = "## Folder layout\n"
assert anchor in t and "## V100 tuning notes" not in t
t = t.replace(anchor, section + anchor, 1)
p.write_text(t, encoding="utf-8")
print("README updated")
