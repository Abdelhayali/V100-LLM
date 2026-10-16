# V100-LLM

**One folder to run the best local LLMs on an NVIDIA Tesla V100 16 GB under Windows.** It includes a GUI to pick a model and
an engine ("kernel"), downloads anything that is missing, tunes every model for a 16 GB V100, gives each model a vision (image)
mode, and ships a test suite that scores models in a leaderboard.

You don't need WSL, Docker, CUDA, Visual Studio or Python: the folder brings its own engines, CUDA runtime and Python.

![leaderboard](eval/results/leaderboard.png)

<!-- LEADERBOARD -->
## Leaderboard

Scores are 0-100 per category (pass rates), and Overall is their mean. Gen tok/s is the mean over replies of 64+ tokens. Prompt tok/s is measured on short prompts; see the model table for long-context prompt speed. Rebuild this table with `EVALUATE.bat`.

| # | Model | Kernel | Size (GB) | Gen tok/s | Prompt tok/s (short) | Coding | Chat & reasoning | Instructions | Web search | Agent | Vision | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MiniCPM-V 4.7 35B-A3B IQ3_XS | llamacpp | 14.5 | 42.7 | 115 | 100 | 83 | 100 | 100 | 100 | 100 | **97.2** |
| 2 | Qwen3.8-27B PXQ3 | pxa | 12.4 | 22.8 | 97 | 100 | 83 | 100 | 100 | 100 | 100 | **97.2** |
| 3 | Underdog Saluki 27B (Qwen3.8 2-bit, MTP) | llamacpp | 8.3 | 52.9 | 84 | 100 | 83 | 100 | 100 | 100 | 100 | **97.2** |
| 4 | Ternary-Bonsai-2-27B Uncensored Heretic | prism | 7.2 | 44.1 | 133 | 100 | 75 | 100 | 100 | 100 | 100 | **95.8** |
| 5 | NVIDIA Nemotron-3.5-Bolt-74B-A9B (2-bit) | llamacpp | 22.0 | 17.8 | 29 | 100 | 92 | 100 | 100 | 100 | 75 | **94.5** |
| 6 | PXA-Fusion4-35B-A3B PXQ2 | pxa | 11.2 | 69.8 | 478 | 83 | 75 | 100 | 100 | 100 | 100 | **93.0** |
| 7 | Ornith-1.5-35B-A3B PXQ2 | pxa | 11.2 | 65.9 | 362 | 83 | 75 | 100 | 100 | 100 | 100 | **93.0** |
| 8 | Strata: Qwen3.8-Flash-Next 125B IQ2_XS | strata | 63.3 | 27.4 | 44 | 100 | 75 | 100 | 83 | 100 | 100 | **93.0** |
| 9 | Qwen3.8-27B HauhauCS Aggressive IQ3_XS | fastmtp | 13.1 | 47.1 | 101 | 100 | 67 | 88 | 100 | 100 | 100 | **92.4** |

> Fusion4 and Ornith: with the model card's repetition penalties they scored **45** and **74**, because the penalties corrupt numbers, code and tool calls (8080 became 80). Their default preset leaves the penalties off, and the penalties are still available as the `creative` preset.
<!-- /LEADERBOARD -->

## Quick start

1. Install an NVIDIA driver from the **R576 series or newer**. A V100 in TCC mode is fine.
2. Download this repository (green **Code → Download ZIP**, or `git clone`), then extract it, for example to `D:\V100-LLM`.
3. Double-click **`START-GUI.bat`**. The first run downloads the portable Python runtime (37 MB), then opens the GUI at
   http://127.0.0.1:7860.
4. Pick a model, then press **Download missing**. That fetches the model files from Hugging Face (checking each one's
   checksum) and the engine from this repo's release.
5. Press **Start**, then chat in the right-hand panel. A live tokens/s meter, prompt speed and image upload are built in.
   Any OpenAI-compatible app can also use `http://127.0.0.1:8899/v1`.

Every parameter is editable in the GUI. **Recommended** restores the tuned values, and **Save .bat** writes a standalone
launcher for your own settings.

## Models (tested on one Tesla V100-SXM2-16GB, Xeon E5-2660 v4, 64 GB DDR4)

| Model | Engine | Size | Context | Speed (gen) | Full-context test | Vision |
|---|---|---|---|---|---|---|
| PXA-Fusion4-35B-A3B PXQ2 | PXA | 11.2 GB | 16k | 64-76 tok/s | – | GPU |
| Ornith-1.5-35B-A3B PXQ2 | PXA | 11.2 GB | 16k | ~60 tok/s | – | GPU |
| Qwen3.8-27B PXQ3 | PXA | 12.4 GB | 8k | ~27 tok/s | – | GPU |
| Qwen3.8-27B HauhauCS IQ3_XS + FastMTP | FastMTP | 12.2 GB | 24k / 80k / 120k | 40-53 tok/s | 118k ✓ | GPU (80k) / CPU (120k) |
| **Underdog Saluki 27B** (2-bit + MTP) | llama.cpp | 8.4 GB | **262k** | 36-52 tok/s | 252k ✓ | CPU |
| **Ternary-Bonsai-2-27B Heretic** PQ2_0 | Prism | 7.2 GB | **262k** | 47-50 tok/s | 252k ✓ | GPU |
| **MiniCPM-V 4.7 35B-A3B** IQ3_XS | llama.cpp | 14.5 GB | **262k** | 39-41 tok/s | 252k ✓ | GPU |
| **NVIDIA Nemotron-3.5-Bolt-74B-A9B** (2-bit) | llama.cpp | 22.0 GB | **262k** | ~20 tok/s | 250k ✓ | CPU |
| **Strata: Qwen3.8-Flash-Next 125B** IQ2_XS | Strata | ~63 GB | **262k** | 12-18 tok/s | – | CPU |

"Full-context test": a prompt of about 250,000 tokens with one secret code hidden in the middle. The model has to return it
exactly. Models bigger than 16 GB (Nemotron, Strata, part of MiniCPM-V) keep some experts in system RAM; they need 32-64 GB of
RAM, and their speed depends on the CPU and memory.

Some of these models are "uncensored" / "abliterated" fine-tunes with their safety tuning removed (Fusion4, HauhauCS, Bonsai
Heretic). Their model cards say so.

## Folder layout

```
START-GUI.bat            the GUI (model + kernel picker, downloads, chat, tokens/s)
EVALUATE.bat             score models and rebuild the leaderboard
catalog.json             every model: files (URL + SHA-256), tuned presets, compatible kernels, measured speeds
gui/                     launcher.py + ui.html (Python standard library only)
models/<model>/
    model/               the model files
    kernel/<engine>/     the engine for this model (hard links into _kernels/, so no extra disk space)
    run-<preset>.bat     standalone launchers (work without the GUI)
_kernels/<engine>/       shared engine store (filled by downloads)
runtime/python/          portable Python 3.12 (+ pylibs for Strata's server)
eval/                    test suite, results, leaderboard
tools/                   how the engines were built (patches, build scripts)
```

The folder is self-contained and can be copied to another PC or drive. Hard links fall back to copies when the target is not
NTFS.

## Engines (kernels)

| Kernel | What it is | Built from |
|---|---|---|
| `pxa` | [PXA](https://github.com/poisonxa16/pxa) ported to Windows/MSVC (PXQ models) | `136f7ac` + `tools/patches/pxa-windows.patch`, CUDA 12.9, sm_70 |
| `fastmtp` | llama.cpp + [HauhauCS FastMTP](https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF) patch | `4df29be` + patch, CUDA 12.9, sm_70 |
| `llamacpp` | upstream [llama.cpp](https://github.com/ggml-org/llama.cpp) (Nemotron-H, MiniCPM-V 4.7, draft-mtp) | `f336359`, CUDA 12.9, sm_70 |
| `prism` | [Prism ML llama.cpp](https://github.com/PrismML-Eng/llama.cpp) (ternary PQ2_0/PTQ1_0 kernels) | official release `prism-b10777`, CUDA 12.4 |
| `strata` | [Strata](https://github.com/niko1221/strata) 0.1.44.1 + its Python server | experimental CUDA 12 engine for Volta (`STRATA_EXPERIMENTAL_SM60`), sm_70 |

CUDA 13 dropped Volta, so every engine here is built with CUDA 12.x for `sm_70`.

## Evaluating models

`EVALUATE.bat` starts each installed model with its recommended preset, runs the test suite and rebuilds
`eval/results/leaderboard.html`, `.png` and `.md`.

```
EVALUATE.bat                     every installed model that has no score yet
EVALUATE.bat saluki-27b          one model
EVALUATE.bat saluki-27b --redo   score it again
```

Six categories, all graded by code with no LLM judge, offline and deterministic (temperature 0, thinking off):

| Category | Tasks | Graded by |
|---|---|---|
| Coding | 12 Python functions | hidden unit tests run on the generated code |
| Chat & reasoning | 12 math / logic / knowledge questions | exact answer |
| Instruction following | 8 IFEval-style rules | rule checkers |
| Web search | 6 questions needing a `web_search` tool (fixed results) | right tool + query (½), answer uses the results (½) |
| Agent | 5 multi-step tool loops (files, calculator, calendar) | final state of the simulated environment |
| Vision | 4 generated images (shapes, text, chart, table) | exact answer |

**Adding a new model:**
1. Add an entry to `tools/catalog-src.json`: files (Hugging Face repo + file name) and a preset (kernel + parameters).
2. Run `runtime\python\python.exe tools\make-catalog.py`. It fills in sizes and SHA-256 sums.
3. Restart the GUI, download the model, press Start to tune it, then run `EVALUATE.bat <id>`.

## Credits and licences

The engines are MIT (PXA, llama.cpp, Prism ML fork, Strata); see the `LICENSES` folder inside each kernel. The CUDA runtime
DLLs are redistributed under the NVIDIA CUDA EULA, and the Microsoft Visual C++ runtime DLLs under the Visual Studio
redistributable terms. Models are not part of this repository: they download from their authors' Hugging Face pages and
fall under those licences. The scripts, GUI, patches and test suite in this repository are MIT licensed.
