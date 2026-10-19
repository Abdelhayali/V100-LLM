# V100-LLM

**One folder to run the best local LLMs on an NVIDIA Tesla V100 16 GB under Windows.** It includes a GUI to pick a model and
an engine ("kernel"), downloads anything that is missing, tunes every model for a 16 GB V100, gives each model a vision (image)
mode, and ships a test suite that scores models in a leaderboard.

You don't need WSL, Docker, CUDA, Visual Studio or Python: the folder brings its own engines, CUDA runtime and Python.

> **New #1 on the leaderboard: OrcaCyber-Nano-1.0 27B (89.8)** at **60 tok/s, 66 tok/s on code** on one V100 16 GB (`fast-32k`, built-in MTP), with presets up to the full 262k context.

## Demo: MiniCPM-V 4.7 35B-A3B at ~90 tok/s on one V100 16 GB

Real-time screen recordings (not sped up) of the `fast-128k` preset: official OpenBMB `mix_q3gud_im` quant, stock llama.cpp,
128k context, vision enabled. The tokens/s counter under each reply is the chat app's own measurement.

| Long story (1,750 tokens) | Code (a calculator) |
|---|---|
| ![MiniCPM-V 4.7 writing a long story at ~90 tok/s](media/minicpm-v-93tps-story.gif) | ![MiniCPM-V 4.7 writing calculator code at ~90 tok/s](media/minicpm-v-93tps-code.gif) |
| [▶ MP4 video](media/minicpm-v-93tps-story.mp4) | [▶ MP4 video](media/minicpm-v-93tps-code.mp4) |

**The GUI** (`START-GUI.bat`): pick a model, preset and engine, load or unload it, edit any parameter, chat with images, and watch live tok/s, VRAM, GPU load, CPU and RAM.

![V100-LLM GUI with MiniCPM-V 4.7 loaded, generating at 92.8 tok/s](media/gui-screenshot.png)

<!-- LEADERBOARD -->
## Leaderboard (hard suite v2)

![leaderboard](eval/results_hard/leaderboard.png)

72 tasks in 7 categories, every one graded by code (see [Evaluating models](#evaluating-models)). Scores are 0-100 per category, and Overall is the mean of the categories. Gen tok/s is the mean generation speed over replies of 64+ tokens; prompt tok/s is measured on short prompts. Every model runs with its recommended preset from `catalog.json`. Rebuild this table with `EVALUATE.bat`.

| # | Model | Kernel | Size (GB) | Context (scored) | Max context on V100 | Gen tok/s | Prompt tok/s (short) | Coding | Reasoning | Instructions | Web search | Agent | Vision | Long context | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | OrcaCyber-Nano-1.0 27B Mix-13G (MTP built in) | llamacpp | 13.0 | 32k | 262k | **60** (code 66)¹ | 501 | 88 | 95 | 58 | 100 | 100 | 88 | 100 | **89.8** |
| 2 | Qwen3.8-27B HauhauCS Aggressive IQ3_XS | fastmtp | 13.1 | 24k | 120k | 42.2 | 387 | 88 | 95 | 50 | 100 | 100 | 88 | 100 | **88.6** |
| 3 | Qwen3.8-27B Unsloth UD-IQ3_S (MTP) | llamacpp | 13.4 | 32k | 262k | 52.1 | 460 | 94 | 100 | 50 | 100 | 100 | 75 | 100 | **88.4** |
| 4 | MiniCPM-V 4.7 35B-A3B Q3 mix (official mix_q3gud_im) | llamacpp | 15.5 | 128k | 262k | 93.4 | 467 | 88 | 100 | 50 | 88 | 100 | 88 | 100 | **87.5** |
| 5 | Qwen3.8-27B Ridge 3.7bpw (MTP) | llamacpp | 12.6 | 32k | 192k | 49.6 | 478 | 88 | 95 | 42 | 100 | 100 | 88 | 100 | **87.4** |
| 6 | MiniCPM-V 4.7 35B-A3B IQ3_XS | llamacpp | 14.5 | 192k | 262k | 84.4 | 535 | 94 | 100 | 42 | 88 | 100 | 88 | 100 | **87.2** |
| 7 | MiniCPM-V 4.7 35B-A3B Uncensored Q4_K-IQ4_XS (AtomicChat) | llamacpp | 20.1 | 262k | 262k | 38.3 | 376 | 88 | 100 | 33 | 100 | 100 | 88 | 100 | **86.9** |
| 8 | MiniCPM-V 4.7 35B-A3B CRACK Q4_K_M (dealignai) | llamacpp | 22.6 | 262k | 262k | 40.5 | 340 | 88 | 95 | 33 | 100 | 100 | 88 | 100 | **86.2** |
| 9 | Strata: Qwen3.8-Flash-Next 125B Q2_0 | strata | 66.4 | 262k | 262k | 34.8 | 1207 | 94 | 90 | 42 | 88 | 100 | 88 | 100 | **85.8** |
| 10 | Strata: Qwen3.8-Flash-Next 125B IQ2_XS | strata | 68.0 | 262k | 262k | 34.1 | 1163 | 88 | 100 | 50 | 88 | 100 | 75 | 100 | **85.7** |
| 11 | Strata: Qwen3.8-Flash-Next 125B Coder IQ1_M | strata | 58.4 | 262k | 262k | 29.7 | 1247 | 94 | 100 | 42 | 88 | 100 | 75 | 100 | **85.4** |
| 12 | Qwen3.8-27B ISTA-DASLab GSQ-RCO-IQ3_S (MTP) | llamacpp | 12.1 | 32k | 192k | 52.4 | 480 | 94 | 95 | 42 | 100 | 100 | 88 | 50 | **81.1** |
| 13 | Qwen3.8-27B Huihui abliterated GSQ-RCO-IQ3_S (MTP) | llamacpp | 12.1 | 32k | 192k | 50.2 | 471 | 69 | 100 | 50 | 100 | 100 | 88 | 50 | **79.5** |
| 14 | NVIDIA Nemotron-3.5-Bolt-74B-A9B (2-bit) | llamacpp | 22.0 | 262k | 262k | 16.7 | 277 | 75 | 85 | 58 | 100 | 100 | 88 | 50 | **79.4** |
| 15 | Qwen3.8-27B HauhauCS Aggressive Q2_K_P (long context) | llamacpp | 10.7 | 160k | 160k | 41.6 | 326 | 75 | 95 | 42 | 100 | 100 | 88 | 50 | **78.5** |
| 16 | Qwen3.8-27B Unsloth UD-Q3_K_XL (DFlash2) | llamacpp | 14.3 | 32k | 32k | 55.4 | 508 | 94 | 90 | 42 | 100 | 100 | 62 | 50 | **76.9** |
| 17 | Ternary-Bonsai-2-27B Uncensored Heretic | prism | 7.2 | 262k | 262k | 39.5 | 363 | 56 | 100 | 42 | 100 | 100 | 88 | 50 | **76.5** |
| 18 | Underdog Saluki 27B (Qwen3.8 2-bit, MTP) | llamacpp | 8.3 | 262k | 262k | 46.8 | 351 | 62 | 95 | 42 | 88 | 100 | 88 | 50 | **74.9** |
| 19 | PXA-Fusion4-35B-A3B PXQ2 | pxa | 11.2 | 16k | 16k | 70.0 | 2384 | 38 | 90 | 25 | 88 | 100 | 75 | 100 | **73.6** |
| 20 | Qwen3.8-27B PXQ3 | pxa | 12.4 | 8k | 8k | 19.8 | 573 | 75 | 95 | 42 | 100 | 100 | 88 | 0 | **71.3** |
| 21 | Ornith-1.5-35B-A3B PXQ2 | pxa | 11.2 | 16k | 16k | 64.1 | 2333 | 50 | 85 | 33 | 100 | 83 | 75 | 0 | **60.9** |

¹ OrcaCyber-Nano: speed of its tuned `fast-32k` preset (MTP 3), measured as code 66.6 / chat 54.0 tok/s (mean 60.3); its mean over all eval replies is 56.9 tok/s.

Notes:
- Long context is a ~14k-token text with three facts hidden in different places that have to be combined. Qwen3.8-27B PXQ3 runs with an 8k context preset, so the text does not fit; Ornith runs with 16k and still answered wrong.
- Fusion4 and Ornith run without the model card's repetition penalties. With them they scored much lower, because the penalties corrupt numbers, code and tool calls (8080 became 80). The penalties are still available as the `creative` preset.
- **Fastest:** MiniCPM-V 4.7 Q3 mix runs at **93 tok/s with 128k context** on the 16 GB V100 (preset `fast-128k`): the vision encoder runs on the CPU, which frees enough VRAM to keep every expert on the GPU. A 120k-token prompt was filled without a crash (36 tok/s while generating at 120k).
- MiniCPM-V 4.7 IQ3_XS reaches **91 tok/s with up to 224k context** (presets `fast-192k` / `fast-224k`) the same way: vision encoder on the CPU, every expert on the GPU. It is 1 GB smaller than the Q3 mix, so the KV cache for 192-224k still fits. At the full 262k, 2 layers of experts go to RAM (60 tok/s, `fast-262k`).
- Strata runs three quantizations of the same 125B model (IQ2_XS, Q2_0 and the Coder IQ1_M with half the experts); they share one 28.8 GB n-gram table that is read from the SSD.
- MiniCPM-V CRACK with its DSpark draft model is slower on a 16 GB card (34 vs 38.5 tok/s): the drafter needs ~1.5 GB of VRAM, so 7 more layers of experts go to RAM, and chat drafts are accepted only ~47% of the time.
- ExLlamaV3 (Qwen3.8-27B EXL3) runs on the V100 but at ~11 tok/s, so it is not scored.
- The older, easier suite (v1) is still in `eval/results/`; most models scored 90-100 there, which is why v2 exists.
<!-- /LEADERBOARD -->

## 📱 Control your V100 from your Android phone and switch models

The **[phone app](phone-app/)** connects your Android phone to this PC through an encrypted Cloudflare tunnel (no port
forwarding), from anywhere:

| | |
|---|---|
| 🔀 **Switch models** | Every model of the catalog with its tuned presets: **Load**, **Switch**, **Reload** or **Unload** with one tap |
| 📊 **Live PC status** | Loaded model plus **VRAM, GPU load, CPU and RAM** bars at the top of every chat, refreshed every 3 s |
| 💬 **Chat** | Streaming replies, sessions, thinking view, tokens/s and context used; the model list follows what is loaded |
| 🖼️ **Vision & files** | Send photos, PDFs and PC screenshots to the vision models; browse and upload files on the PC |
| 🔊 **Read aloud** | Replies spoken in Arabic and English (detected per sentence), per reply or automatically |
| 📝 **Notes, tasks & calendar** | Stored on the PC and used by the model: "what tasks do I have?", "remind me…", "what's tomorrow?" |
| 📧 **Gmail & Google Calendar** | Read email, draft replies, list / add events; sending always waits for your approval |
| 🔎 **Deep research** | Drawer → Deep research: the PC plans searches, reads the pages, takes notes, looks for gaps and writes a report with numbered sources (quick / normal / deep); saved as a chat and a .md file, notification when ready |
| 🎙 **Voice notes / meetings** | Record on the phone (keeps going with the screen off); the PC transcribes with Whisper large-v3-turbo (Arabic + English) and writes title, summary, key points, decisions and action items, which can go straight to your tasks |
| 📁 **Long-term projects** | A goal, living notes and a folder shared by all the project's chats; the AI records progress with `project_note`, and a daily schedule can keep working on it |
| 🧾 **Audit log** | Every tool action the AI took - code, files, email, OCR, schedules - with time, chat, approval and result, searchable in the app |
| 🏠 **Assistant button** | Set LocalAI Bridge as the phone's digital assistant: long-press home opens it listening, with a screenshot of the screen attached so you can ask about it |
| ⏰ **Scheduled tasks** | Drawer → Schedules & alerts: a prompt the PC runs by itself (daily at a time, or every N minutes), e.g. "summarize my unread email" at 8:00, in its own chat with the access you give it; a notification when it is done |
| 🌡 **Temperature alerts** | Your own GPU / CPU limits; a notification when one is passed (checked every 30 s on the PC) |
| 🎤 **Voice chat** | Mic button in the chat: speak (Arabic or English), the reply is read aloud; a **Stop reading** button while it talks |
| 🚗 **Driving mode** | Hands-free: tap the car icon (or the "Driving mode" app shortcut) once, then it listens (Arabic by default, English too; switch on the driving screen), sends, reads the short spoken answer and listens again - no touching. Say "new chat" or "stop" (also in Arabic). One beep per turn; screen stays on |
| 🌐 **Translator** | Drawer → Translator: 🎤 Arabic → English or 🎤 English → Arabic (or type), the translation is read aloud. Uses the PC's model directly, no chat history |
| 📷 **Ask about a photo** | 📎 → Ask about a photo: take a picture, ask your question by voice, hear the answer (vision model or OCR) |
| 📤 **Share to the app** | Share a photo, screenshot, PDF, link or text from any app straight into a chat |
| 🧩 **Home-screen widget** | GPU status (model, VRAM, GPU / CPU temperature) with Ask and Voice buttons |
| 🛡 **Sandbox for code** | Per chat (📎 menu → Run code in sandbox): the AI's code runs in a Windows AppContainer - no network, no access to your files, 4 GB memory cap, killed at the time limit. Packages already installed (numpy, matplotlib) work, and sandboxed code needs no approval. No admin rights or installs |
| 🔔 **Reply ready** | A notification when a reply finishes while the app is in the background, and a short sound when it finishes while the chat is open (both can be turned off in Settings) |
| 🌡 **GPU / CPU status** | Models tab: VRAM, GPU load, **temperature, power, clock and throttle reason**, CPU, RAM; CPU temperature when LibreHardwareMonitor runs on the PC. **Free GPU** ends the model, a stuck OCR and leftover processes |
| 📊 **Benchmark from the phone** | Models tab: speed test and any categories of the hard suite on the loaded model (results stay on the PC in `eval/results_phone`, the public leaderboard is not changed) |
| 🔁 **Crash recovery** | If the model server dies after it was ready, the launcher starts the same preset again (at most 3 times in 10 minutes) |
| 🔑 **Change access key** | Settings → Change access key: a new key at once, the old key and QR stop working |
| 📄 **OCR sub-model** | [baidu/Unlimited-OCR](https://huggingface.co/baidu/Unlimited-OCR) (MIT) reads scanned PDFs, photos of pages and text in images (tables, formulas, Arabic and English) for the chat model through an `ocr_document` tool. Choose per chat: **Off**, **A: GPU** (unloads the chat model, reads on the V100, loads it again) or **B: CPU** (the chat model stays loaded). Install once with `phone-app/ocr/setup-ocr.bat` (~10 GB) |
| 🧠 **Thinking effort** | Off / Low / Medium / High / Max per chat (a llama.cpp thinking budget: 1k / 4k / 16k tokens / unlimited), so a reply never spends all its tokens thinking |
| 🔑 **OpenAI API anywhere** | An OpenAI-format URL + API key (made and refreshed in the app) for the loaded model; same URL after switching models |
| ❓ **Choices** | When the model needs a decision it asks with buttons and waits; listed options become tap-to-answer chips |
| 👁️ **See every step** | A live step list of what the model does on the PC (code, files, search, questions) with now / waiting / done |
| 🖥️ **Tools** | The model can run code, read files, search the web, draw charts and remember facts (you approve each action) |
| 🤖 **Code agent (beta)** | OpenCode working on a project folder of your PC with the loaded model |

**💻 Windows desktop app:** the same features on a laptop screen: [`desktop-app/release/LocalAI-Bridge-Desktop.exe`](desktop-app/release/LocalAI-Bridge-Desktop.exe) (one file, about 8 MB, no install). See [desktop-app/README.md](desktop-app/README.md).

![LocalAI Bridge Desktop on Windows](media/desktop-app.png)

**Get it:** install [`phone-app/release/LocalAI-Bridge-V100.apk`](phone-app/release/LocalAI-Bridge-V100.apk) (Android 8+),
run `phone-app\Start-Server.bat` on the PC (needs Python 3.10+), and scan the QR code it shows. The V100-LLM launcher is
started automatically when the phone needs it. Details: [phone-app/README.md](phone-app/README.md).

## Quick start (fresh Windows PC)

**You need:** Windows 10 or 11 (64-bit), an NVIDIA Tesla V100 16 GB (other 16 GB NVIDIA cards from Volta on work too),
32 GB of system RAM (64 GB for the 262k-context and Strata presets) and about 20 GB of free disk per model (an SSD
loads models much faster). Nothing else: no Python, CUDA, WSL or Docker. Engines and the Python runtime come with the folder.

1. Install an NVIDIA driver from the **R576 series or newer**. A V100 in TCC mode is fine.
2. Download this repository (green **Code → Download ZIP**, or `git clone`), then extract it, for example to `D:\V100-LLM`.
   Avoid a path with spaces or one under OneDrive.
3. Double-click **`START-GUI.bat`**. The first run downloads the portable Python runtime (37 MB), then opens the GUI at
   http://127.0.0.1:7860.
4. Pick a model, then press **Download missing**. That fetches the model files from Hugging Face (checking each one's
   SHA-256) and the engine from this repo's release.
5. Pick a preset (the first one, **FAST**, is the tuned default), press **Start**, then chat in the right-hand panel. A live
   tokens/s meter, prompt speed and image upload are built in. Any OpenAI-compatible app can also use
   `http://127.0.0.1:8899/v1`.

Every parameter is editable in the GUI. **Recommended** restores the tuned values, and **Save .bat** writes a standalone
launcher for your own settings. Each model folder also has ready `run-<preset>.bat` files that work without the GUI.

### Gated models (OrcaCyber-Nano): sign in once

Some authors require you to accept their terms on Hugging Face before downloading. The launcher then uses your own token:

1. Create a free account at [huggingface.co](https://huggingface.co/join) and sign in.
2. Open the model page and press **Agree and access repository** (for OrcaCyber-Nano:
   [orcarouter/OrcaCyber-Nano-1.0](https://huggingface.co/orcarouter/OrcaCyber-Nano-1.0); access is granted at once).
3. Create a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (type **Read**).
4. Save it as a text file **`hf-token.txt`** in the V100-LLM folder (just the token, one line). Alternatively set the
   `HF_TOKEN` environment variable, or run `hf auth login` if you have the Hugging Face CLI. The token is only sent to
   huggingface.co, and `hf-token.txt` is ignored by git, so it never ends up in a commit.
5. Press **Download missing** again. Without access, the GUI tells you which page to open.

### Install OrcaCyber-Nano-1.0 27B on a V100 16 GB (#1 on the leaderboard)

1. Do steps 1-3 of the quick start above, then the gated-model steps (accept access + `hf-token.txt`).
2. In the GUI pick **OrcaCyber-Nano-1.0 27B Mix-13G (MTP built in)** and press **Download missing**: 13.0 GB model +
   0.9 GB vision projector, plus the `llamacpp` engine (V100-tuned build) from the release. About 14 GB in total.
3. Choose a preset and press **Start**:

   | Preset | Context | Speed on V100 16 GB | Use it for |
   |---|---|---|---|
   | **FAST: 32k, MTP 3** | 32k | **60 tok/s** (66 on code) | chat, coding, images: the default |
   | 96k, MTP 3, q4 KV | 96k | 57 tok/s | long files and documents |
   | 160k, no MTP | 160k | 32 tok/s | very long documents |
   | FULL 262k, KV streaming (`kvstream` engine) | 262k | 24 tok/s at 20k, slower as it fills | the full context, text only, needs 64 GB RAM |

4. Chat in the GUI, connect any OpenAI-compatible app to `http://127.0.0.1:8899/v1`, or use the phone / desktop app below
   (Models screen → OrcaCyber-Nano → preset). Without the GUI: run `models\orcacyber-nano\run-fast-32k.bat`.

Recommended sampling: temperature 0.7, top-k 20, top-p 0.8 (the presets set these). For precise formatting tasks, turn
thinking to **Low** in the apps.

### Fixed address for the phone (named Cloudflare tunnel)

The default quick tunnel gets a new random address every time the bridge restarts, so the phone must re-scan the QR. A
named tunnel keeps one address for good (free Cloudflare account + a domain on Cloudflare):

1. In the Cloudflare dashboard: **Zero Trust → Networks → Tunnels → Create a tunnel** (type Cloudflared), name it, and
   copy the **token** from the install command it shows.
2. Add a **public hostname**, e.g. `ai.yourdomain.com`, service **HTTP** → `127.0.0.1:8766` (the bridge port in
   `phone-app/server/config.json`).
3. In `phone-app/server/config.json` set `"tunnel_mode": "named"`, `"tunnel_token": "<the token>"` and
   `"public_url": "https://ai.yourdomain.com"`, then restart the bridge and scan its QR once.

From then on the address never changes. If a phone or QR is lost, use **Settings → Change access key** in the app: the
old key stops working at once, and other devices re-pair with the new QR.

### Troubleshooting

- **"needs the Microsoft Visual C++ Redistributable"**: install
  [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe) (only the Prism engine relies on it; the others
  ship their own runtime).
- **Out of memory when starting or on a long prompt**: choose a preset with a shorter context, and make sure nothing else
  uses the GPU (`nvidia-smi`). On a card that also drives a display, about 0.5-1 GB less VRAM is free.
- **The first start of a model is slow**: the file is read from disk once (an HDD takes minutes), then it stays cached.
- **Qwen3.8-27B EXL3 (ExLlamaV3, experimental)** cannot be downloaded: its engine is a local TabbyAPI build. Every other model installs with **Download missing**.
- **Port 7860 or 8899 already in use**: close the other program, or start the server with `set PORT=8900` before a
  `run-<preset>.bat`.

## Models (tested on one Tesla V100-SXM2-16GB, Xeon E5-2660 v4, 64 GB DDR4)

| Model | Engine | Size | Context | Speed (gen) | Full-context test | Vision | System RAM used | Best for |
|---|---|---|---|---|---|---|---|---|
| **MiniCPM-V 4.7 35B-A3B Q3 mix** (official mix_q3gud_im) | llama.cpp | 15.5 GB | **128k** / 262k | **93 tok/s** at 128k, 70 at 262k | 120k ✓ | CPU | ~2 GB (128k: all experts on GPU) | **best all-rounder** |
| **Qwen3.8-27B HauhauCS IQ3_XS** + FastMTP | FastMTP | 12.2 GB | 24k / 80k / 120k | 40-53 tok/s | 118k ✓ | GPU (80k) / CPU (120k) | ~2 GB | top score, uncensored |
| **Qwen3.8-27B Unsloth UD-IQ3_S** + MTP / DFlash2 (official) | llama.cpp (V100 patch) / kvstream | 12.0 GB (+1.1-1.4 GB drafter) | 32k / 96k / 192k / **262k** | **55 tok/s** at 32k (MTP), **58** at 96k (DFlash2, code ~73), 31 at 192k; full 262k: 12 / 9 / 6 tok/s at a filled 99k / 185k / 257k | 257k ✓ (streaming) | CPU | ~2 GB (+ KV in RAM for 262k) | official 27B, fast MTP, **full context** |
| Qwen3.8-27B Unsloth UD-Q3_K_XL + DFlash2 (official) | llama.cpp | 13.2 GB (+1.1 GB drafter) | 32k | 55 tok/s (DFlash2, code ~70) | not run yet | CPU | ~2 GB | same speed as IQ3_S, lower score (76.9) |
| **OrcaCyber-Nano-1.0 27B Mix-13G** (orcarouter, MTP built in; gated, sign in to download) | llama.cpp (V100 patch) / kvstream | 13.0 GB | 32k / 96k / 160k / **262k** | **60 tok/s** at 32k (MTP 3, code 66), 57 at 96k, 32 at 160k, 24 at 20k filled with 262k streaming | 19.6k ✓ all presets | CPU | ~2 GB (+ KV in RAM for 262k) | **#1 overall (89.8)**: fastest dense 27B here, cybersecurity + coding |
| **Qwen3.8-27B Ridge 3.7bpw** (empero-ai, built-in MTP) | llama.cpp | 12.6 GB | 32k / 96k / 192k | 50 tok/s at 32k, 48 at 96k, 27 at 192k (no MTP) | not run yet | CPU | ~2 GB | official, balanced (87.4) |
| Qwen3.8-27B ISTA-DASLab GSQ-RCO-IQ3_S (built-in MTP) | llama.cpp | 12.1 GB | 32k / 96k / 192k | 52 tok/s at 32k, 52 at 96k, 27 at 192k (no MTP) | not run yet | CPU | ~2 GB | official, coding 94 |
| Qwen3.8-27B Huihui abliterated GSQ-RCO-IQ3_S (built-in MTP) | llama.cpp | 12.1 GB | 32k / 96k / 192k | 52 tok/s at 32k, 51 at 96k, 29 at 192k (no MTP) | not run yet | CPU | ~2 GB | uncensored |
| **MiniCPM-V 4.7 35B-A3B** IQ3_XS | llama.cpp | 14.5 GB | **192k** / 224k / 262k | **91 tok/s** up to 224k, 60 at 262k | 252k ✓ | CPU (fast presets) | ~2 GB (192k: all experts on GPU) | **fast + long context**, coding |
| MiniCPM-V 4.7 35B-A3B Uncensored Q4_K-IQ4_XS (AtomicChat) | llama.cpp | 20.1 GB | **262k** | 33-38 tok/s | not run yet | GPU | ~9.5 GB (7.9 GB experts) | uncensored + long context |
| MiniCPM-V 4.7 35B-A3B CRACK Q4_K_M (dealignai) | llama.cpp | 22.5 GB | **262k** | 37-40 tok/s (DSpark: slower, see note) | not run yet | GPU | ~11.5 GB (9.9 GB experts) | uncensored |
| Qwen3.8-27B HauhauCS Q2_K_P | llama.cpp | 10.7 GB | **160k** | ~42 tok/s | not run yet | CPU | ~3 GB | long context on the 27B |
| **Ternary-Bonsai-2-27B Heretic** PQ2_0 | Prism | 7.2 GB | **262k** | 40-50 tok/s | 252k ✓ | GPU | ~2 GB | smallest |
| **Underdog Saluki 27B** (2-bit + MTP) | llama.cpp | 8.4 GB | **262k** | 36-52 tok/s | 252k ✓ | CPU | ~3 GB | |
| PXA-Fusion4-35B-A3B PXQ2 | PXA | 11.2 GB | 16k | 64-76 tok/s | – | GPU | ~2 GB | speed |
| Ornith-1.5-35B-A3B PXQ2 | PXA | 11.2 GB | 16k | ~60 tok/s | – | GPU | ~2 GB | |
| Qwen3.8-27B PXQ3 | PXA | 12.4 GB | 8k | 20-27 tok/s | – | GPU | ~2 GB | |
| **NVIDIA Nemotron-3.5-Bolt-74B-A9B** (2-bit) | llama.cpp | 22.0 GB | **262k** | 17-20 tok/s | 250k ✓ | CPU | ~9 GB | instruction following |
| **Strata: Qwen3.8-Flash-Next 125B** Q2_0 | Strata | 66.4 GB | **262k** | ~35 tok/s | – | CPU | ~38 GB experts (+29 GB table read from SSD) | coding |
| Strata: Qwen3.8-Flash-Next 125B IQ2_XS | Strata | 68 GB | **262k** | ~34 tok/s | – | CPU | ~39 GB experts (+29 GB table read from SSD) | |
| Strata: Qwen3.8-Flash-Next 125B Coder IQ1_M | Strata | 58.4 GB | **262k** | ~30 tok/s | – | CPU | ~30 GB experts (+29 GB table read from SSD) | coding, less RAM |

Every preset is tuned to fill the 16 GB of VRAM (about 15-15.5 GB used). "System RAM used" is the MoE expert weights kept in
RAM (`--n-cpu-moe`, measured from the GGUF tensors) plus ~1.5 GB for the engine itself; the vision encoder adds ~1 GB when it
runs on the CPU. CPU threads: the MiniCPM-V presets use `-t 14`, the others the engine default (one per physical core). The
CPU only does real work for models that keep experts or the vision encoder in RAM.

"Full-context test": a prompt of about 250,000 tokens with one secret code hidden in the middle. The model has to return it
exactly. Models bigger than 16 GB (Nemotron, Strata, part of MiniCPM-V) keep some experts in system RAM; they need 32-64 GB of
RAM, and their speed depends on the CPU and memory.

Some of these models are "uncensored" / "abliterated" fine-tunes with their safety tuning removed (Fusion4, HauhauCS, Bonsai
Heretic). Their model cards say so.

## V100 tuning notes

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
| `llamacpp` | upstream [llama.cpp](https://github.com/ggml-org/llama.cpp) (Nemotron-H, MiniCPM-V 4.7, draft-mtp, DFlash2) with the **V100 decode patch** (see below) | `f336359` + [`patches/llamacpp-f336359-v100-mmvq.patch`](patches/llamacpp-f336359-v100-mmvq.patch), CUDA 12.9, sm_70 |
| `kvstream` | [llama.cpp adaptive KV streaming](https://github.com/RaymondHuang210129/llama.cpp-adaptive-kv-streaming): KV cache in system RAM, streamed through a VRAM arena, so Qwen3.8-27B runs the **full 262k context** on 16 GB | `db8fd5d`, CUDA 12.9, sm_70, FA pairs f16/q8_0-q4_0/q4_0-q4_0/q8_0-q8_0 |
| `prism` | [Prism ML llama.cpp](https://github.com/PrismML-Eng/llama.cpp) (ternary PQ2_0/PTQ1_0 kernels) | official release `prism-b10777`, CUDA 12.4 |
| `strata` | [Strata](https://github.com/niko1221/strata) 0.1.44.1 + its Python server | experimental CUDA 12 engine for Volta (`STRATA_EXPERIMENTAL_SM60`), sm_70 |

CUDA 13 dropped Volta, so every engine here is built with CUDA 12.x for `sm_70`.

## Evaluating models

`EVALUATE.bat` starts each installed model with its recommended preset (it starts the GUI launcher in the background if it is not running), runs the hard test suite (v2) and rebuilds `eval/results_hard/leaderboard.html`, `.png` and `.md`.

```
EVALUATE.bat                              every installed model that has no score yet
EVALUATE.bat saluki-27b                   one model
EVALUATE.bat saluki-27b:262k              one model, a specific preset
EVALUATE.bat saluki-27b --redo            score it again
EVALUATE.bat saluki-27b --redo --only=coding   re-run one category and merge it into the old result
EVALUATE.bat --basic                      the older, easier suite (v1, eval/results/)
```

Then `runtime\python\python.exe tools\readme-leaderboard.py` copies the new table into this README.

### How the hard suite works

The first suite (v1) was too easy: most models scored 90-100, so it could not tell them apart. The hard suite (v2) is built
so that no 16 GB-class model gets everything right. It has 72 tasks in 7 categories:

| Category | Tasks | What the model has to do | Graded by |
|---|---|---|---|
| Coding | 16 | Write Python functions with traps: an expression parser without `eval`, regex matching, Dijkstra with tie-breaking, LRU cache with TTL, topological sort, edit distance, Roman numerals, sudoku, knapsack, spiral matrix, JSON minifier... | hidden edge-case unit tests run on the generated code (sandboxed, with a timeout) |
| Reasoning | 20 | Multi-step math, logic, dates, combinatorics and word problems | exact answer on the last line |
| Instructions | 12 | Follow 3-5 rules at once (word counts, forbidden letters, exact formats, ordering, JSON shape...) | rule checkers; all rules of a task must hold |
| Web search | 8 | Multi-hop questions: search, read the result, search again with what was found, sometimes compute with a `calculator` tool | right answer, and the minimum number of distinct searches; the "web" is a fixed offline index of 13 pages |
| Agent | 6 | Work on a small simulated project with file tools and `run_tests`: fix a bug, add a function, rename across files, fix a config, build a CSV report | the final state of the files and the project's own tests |
| Vision | 8 | Generated images: sum a table column, look up a row, read a bar chart, count dots, read small text, spatial relations, an analog clock, a receipt | exact answer |
| Long context | 2 | A ~14k-token text with three facts hidden far apart that have to be combined (a vault code split in 3 parts, a chain of ages) | exact answer |

Rules that keep the results fair and repeatable:
- **No LLM judge.** Everything is checked by code, so the same answer always gets the same score.
- **Deterministic and offline:** temperature 0, thinking off, no internet access (web search uses the fixed index).
- **Same preset as users get:** each model runs with its recommended GUI preset, so the speed and score match what you see.
- **Every task is proven solvable:** `eval/reference_solutions.py` holds a correct solution for every coding and agent task, and
  `selftest_hard.py` / `selftest_agent.py` check that they pass the graders. Computed answers (dates, sums,
  codes) are asserted in `tasks_hard.py`.
- **Answer extraction:** the model may think out loud; the grader takes the final line. Tool calls are accepted in the OpenAI
  format and in the Qwen XML / `<tool_call>` text formats.
- **Score:** each category is the percentage of passed tasks; Overall is the mean of the 7 categories (each category weighs
  the same). Speed (gen tok/s) is the mean over replies of 64+ tokens during the run.

Every run is saved in `eval/results_hard/<model>.json` with each task's answer and pass/fail, so you can see why a model lost
points.

**Adding a new model:**
1. Add an entry to `tools/catalog-src.json`: files (Hugging Face repo + file name) and a preset (kernel + parameters).
2. Run `runtime\python\python.exe tools\make-catalog.py`. It fills in sizes and SHA-256 sums.
3. Restart the GUI, download the model, press Start to check it works, then run `EVALUATE.bat <id>`.

**Adding new tasks:** add them to `eval/tasks_hard.py` (and a reference solution for coding/agent tasks), run
`selftest_hard.py`, then re-score with `EVALUATE.bat --redo --only=<category>`.

## Credits and licences

The engines are MIT (PXA, llama.cpp, Prism ML fork, Strata); see the `LICENSES` folder inside each kernel. The CUDA runtime
DLLs are redistributed under the NVIDIA CUDA EULA, and the Microsoft Visual C++ runtime DLLs under the Visual Studio
redistributable terms. Models are not part of this repository: they download from their authors' Hugging Face pages and
fall under those licences. The scripts, GUI, patches and test suite in this repository are MIT licensed.
