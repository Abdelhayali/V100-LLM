# V100-LLM Phone App (LocalAI Bridge V100)

**Control your V100 from your Android phone: switch models, load / unload them, watch the GPU, and chat with the
loaded model from anywhere.** A version of [LocalAI Bridge](https://github.com/Abdelhayali/LocalAI-Bridge) wired to the
V100-LLM launcher.

What this version adds:
- **Models screen** (menu → *Models (load / unload)*): every model of the V100-LLM catalog with its size, vision badge and
  tuned presets. **Load**, **Switch to this**, **Reload** or **Unload** with one tap; the measured speed of each preset is shown.
- **Live PC status bar** at the top of every chat and in the menu: loaded model (ready / loading / none), **VRAM, GPU
  load, CPU and RAM**, refreshed every 3 s. Tap it to open the Models screen.
- The chat's model list follows whatever is loaded on the PC.
- **Choices:** when the model needs you to decide, it asks with buttons (one or several options, or your own answer) and its reply waits on the PC until you tap. Options it lists in plain text get tap-to-answer chips.
- **OpenAI API for any app:** menu → *API* shows an OpenAI-compatible base URL (`<tunnel URL>/openai/v1`) and an API key made and refreshed in the app. It always serves the model loaded on the PC, so it keeps working when you switch models. Copy-ready curl and Python examples included.
- **🔊 Read aloud in Arabic and English:** a speaker button on every reply, or Settings → *Read replies aloud* for every reply. The language is detected per sentence, so mixed replies switch voice; speed is adjustable. Uses the phone's own voices (offline).
- **📝 Notes, tasks & calendar** (menu → *Notes, tasks & calendar*): stored on the PC and shared with the model, so you can say "remind me to call Sara on Friday" or ask "what tasks do I have?" / "what's on my calendar tomorrow?" in English or Arabic.
- **📧 Gmail + Google Calendar (optional):** connect your Google account once (your own OAuth client, login kept on the PC). The model can read email, write draft replies, list and add Google events. **Sending an email or adding a Google event always asks you first**, showing the full email, even with auto-approve on.
- **📬 Tasks from email:** the *From email* tab lets the AI read your recent Gmail and suggest tasks (deadlines, replies, payments). Each one waits for you: **Add to my tasks** or **Dismiss**. Already-read emails are skipped next time. Drafts can be edited by hand or by the AI, and sent after a confirm step.
- **🔒 Access switches:** *Email access* and *Tasks & calendar access* in the chat's paperclip menu, both **off by default**. When off, the model gets no such tools and the server refuses them. An *Ask the AI* button turns on only what it needs, for that one request.
- **✉ Replies from email:** the email scan also finds emails where someone is waiting for your answer (*Needs your reply*); once added to your tasks, tapping one asks the AI to draft the reply.
- **See exactly what it does:** a step list in the chat shows every action on the PC (run code with its first lines, read / write which file, search, ask you) with a live status (now, waiting for you, done, failed), or the model's own plan when it sends one. The status line names the current action.
- The V100-LLM launcher is started on the PC automatically when the phone needs it.

How it fits together:
```
Android app ──HTTPS──► Cloudflare tunnel ──► bridge server (this folder, 127.0.0.1:8765)
                                               ├─ /api/v100/*  ──► V100-LLM launcher (127.0.0.1:7860): models, load, unload, GPU/CPU/RAM
                                               └─ chat / tools ──► loaded model (127.0.0.1:8899, OpenAI API)
```

Setup:
1. Run `START-GUI.bat` in the V100-LLM folder once (or let the bridge start the launcher itself).
2. Run `phone-app\Start-Server.bat` (needs Python 3.10+ on the PC; it creates its own environment on first run).
3. Install `release/LocalAI-Bridge-V100.apk` on the phone (Android 8+) and scan the pairing QR the server shows.

Settings live in `server/config.json` (created on first run): `launcher_url`, `launcher_dir` (found automatically when
this folder is inside V100-LLM) and `llm_base_url` (`http://127.0.0.1:8899`). The app's package is
`com.localai.bridge.v100`, so it installs next to the original LocalAI Bridge app.

---
**Use the AI model running on your Windows PC from your Android phone, from anywhere.**

LocalAI Bridge connects an Android app to a local LLM (llama.cpp, Ollama, LM Studio...) through an
encrypted Cloudflare tunnel. No port forwarding and no cloud AI: your model, your PC, your data.
The assistant can **run code on the PC, browse and read your folders, read PDFs and images, take
screenshots, draw charts, and remember things across chats**.

<p align="center">
  <img src="docs/images/app-chat.jpg" width="200" alt="Chat">
  <img src="docs/images/app-sessions.jpg" width="200" alt="Sessions and menu">
  <img src="docs/images/app-screenshot-tool.jpg" width="200" alt="PC screenshot shown in chat">
  <img src="docs/images/app-approval.jpg" width="200" alt="Approve code before it runs">
</p>
<p align="center"><img src="docs/images/server-control-panel.png" width="700" alt="Windows control panel"></p>

```
Android app ──HTTPS──► Cloudflare tunnel ──► LocalAI Bridge server (127.0.0.1:8765) ──► llama.cpp / Ollama / LM Studio
                                                    │
                                                    ├─ chat sessions + long-term memory (SQLite)
                                                    ├─ tools: run code, files, screenshots, charts, memory
                                                    └─ uploads: PDF text extraction, images for vision models
```

---

## Features

| | |
|---|---|
| 💬 **Chat** | Streaming replies, multiple sessions (rename / delete), pick any loaded model, show the model's "thinking" |
| ✏️ **Messages** | Copy any message, edit a sent message (the chat continues from there), regenerate the last answer |
| 🖥️ **Run code on the PC** | Python, PowerShell or cmd, by the AI or by you from the Terminal screen. Approval on the phone first |
| 📁 **Files on PC** | Browse allowed folders, open/share files, upload from phone to PC, "Ask AI about this file" |
| 🖼️ **Images** | Attach photos/images/PDFs/camera shots, screenshot your PC, charts the AI draws appear inline. Tap to zoom, share or save |
| 🌐 **Web search** | Tap 🌐 in the chat: the AI can search the internet (DuckDuckGo, no API key) and read web pages |
| 📊 **Live status & stats** | See what the PC is doing (reading, thinking, writing, running a tool) with tokens, speed and a timer. Each chat shows context used / available and tokens per second |
| ⚡ **Auto-approve** | Optional: let the AI run code and write files without asking (Settings, with a warning) |
| 🤖 **Code agent (beta)** | [OpenCode](https://opencode.ai) works on any project folder of your PC with your local model: reads code, edits files, runs commands. Every edit and command asks for approval (or per-session auto-approve) |
| 🧠 **Memory** | The AI saves facts about you that carry across all chats. View, add or delete them in the app |
| 🌗 **Themes** | Light, dark or follow the system |
| 🔒 **Security** | 256-bit token, HTTPS tunnel, server only listens on localhost, approval for code and file writes |

---

## How to run it

### What you need

- **Windows 10/11 PC** with **Python 3.10+** ([python.org](https://www.python.org/downloads/), tick *"Add python.exe to PATH"* when installing)
- A **local LLM server** with an OpenAI-compatible API, for example:
  - **llama.cpp** (default): `llama-server -m your-model.gguf --port 8080 --jinja`
    (`--jinja` lets the model use tools)
  - **Ollama**: install it, then `ollama pull qwen2.5:7b` (URL `http://127.0.0.1:11434`)
  - **LM Studio**: start the local server (URL `http://127.0.0.1:1234`)
- An **Android phone** (Android 8.0 or newer)

> For tools (running code, files, screenshots) use a model that supports function calling: Qwen 2.5 / 3,
> Llama 3.1+, Mistral, etc. To let the model *see* images you attach, use a vision model (Qwen2.5-VL, LLaVA, Gemma 3...).

### Step 1: Download the project

```bash
git clone https://github.com/Abdelhayali/LocalAI-Bridge.git
```

Or click **Code → Download ZIP** on GitHub and extract it.

### Step 2: Start your LLM

Start llama.cpp (or Ollama / LM Studio) and leave it running. Check it works by opening
<http://127.0.0.1:8080/v1/models> in a browser. You should see your model listed.

### Step 3: Start the server

Double-click **`Start-Server.bat`**.

- The first run creates a Python environment and installs the packages (takes a few minutes, once).
- The **control panel** opens and starts automatically:
  1. The API server starts on `127.0.0.1:8765`.
  2. A Cloudflare tunnel starts. `cloudflared` is downloaded automatically if it isn't installed.
  3. After 5-20 seconds the **Public URL** and a **QR code** appear.
- **LLM server URL** shows `● online` when your model is reachable. **Default model** lists the models
  it found (click *Refresh models* after loading a new one).

No window? Use **`Start-Server-Console.bat`** instead. It does the same in a console and prints the QR as text.

### Step 4: Install the app on your phone

1. Download **[`release/LocalAI-Bridge.apk`](release/LocalAI-Bridge.apk)** to your phone.
2. Open it and allow *"Install unknown apps"* when Android asks.

### Step 5: Pair the phone

Open the app and choose one:
- **Scan QR code with camera**: point the camera at the QR in the control panel, or
- **Load QR from image / screenshot**: pick a picture of the QR from your gallery (handy when you're not at the PC).

(Or type the **Public URL** and the **Access token**: tick *Show* in the control panel and use *Copy*.)

### Step 6: Use it

- **Chat:** type a message. Tap the model name under the title to switch models.
- **📎 Attach:** image, PDF, any file, camera photo, or **Screenshot of PC**.
- **Ask it to act:** *"take a screenshot of my PC"*, *"plot sin and cos with matplotlib"*,
  *"list the files in my Downloads folder"*, *"read report.pdf and summarize it"*.
  When the AI wants to run code or write a file, the phone asks **Approve / Deny** first.
- **☰ Menu:** your sessions, **Files on PC**, **Terminal**, **Memory**, **Settings**, and the 🌙 theme toggle.
- **Under each message:** 📋 copy, ✏️ edit (your messages), 🔄 regenerate (last answer).
- **🌐 button** (next to 📎): turns web search on or off.
- **While it works:** the bar above the input shows the current step, tokens, speed (t/s) and elapsed time.
  If the PC goes silent for 30 s you get a warning.
- **Under the title:** `Context 1.8k / 131k (1%) · 46.7 t/s · read 297 t/s` for the current chat.
- **Settings → Auto-approve everything:** skips the Approve / Deny step. ⚠️ Only use it with content you trust.

> ⚠️ The free Cloudflare URL **changes every time the server restarts**, so re-scan the QR after a restart
> (Settings → Disconnect / re-pair). For a permanent address, see *Named tunnel* below.

---

## Code agent (beta): OpenCode on your PC

☰ → **Code agent (beta)** lets [OpenCode](https://opencode.ai) work on a project folder of your PC with your
local LLM. It searches and reads code, edits files and runs commands.

1. Install OpenCode once on the PC:
   ```bash
   npm install -g --allow-scripts=opencode-ai opencode-ai
   ```
2. In the app: **New agent session**, pick a project folder (you can create or rename folders there),
   then describe a task, e.g. *"add input validation to app.py and run the tests"*.
3. Every file edit, shell command and web fetch asks for approval: **Allow / Always / Reject**,
   with the exact diff or command shown. The **Auto-approve** switch in the session skips this.
4. Working agents appear in **Running tasks** (Open / Stop), and **Kill all** stops them too.

The bridge starts its own OpenCode server (localhost only, random password) and generates its config
from the bridge settings (`server/data/opencode/opencode.json`). Only folders in `allowed_roots` can be used.
To give it the whole PC, set `"allowed_roots": ["*"]` (every drive).

## Configuration: `server/config.json`

Created on the first run. Click **Open config.json** in the control panel, edit it, then restart the server.

| Key | Default | Meaning |
|---|---|---|
| `llm_base_url` | `http://127.0.0.1:8080` | Your LLM server (`/v1` is added automatically) |
| `default_model` | `""` | Empty = first model the LLM server reports |
| `allowed_roots` | your user folder + `workspace` | **Only** these folders are visible to the app and the AI. Add e.g. `"D:\\"`, or `"*"` for every drive |
| `workspace` | `<project>\workspace` | Where the AI's code runs and saves files |
| `enable_code_exec` | `true` | Allow running code at all |
| `require_tool_approval` | `true` | Phone must approve code runs and file writes |
| `port` | `8765` | Local port (a free one is picked automatically if busy) |
| `tunnel_mode` | `quick` | `quick` (random URL, no account), `named` (fixed URL), `off` (local only) |
| `tunnel_token`, `public_url` | | For a named tunnel |

**Named tunnel (permanent URL):** in the Cloudflare Zero Trust dashboard create a tunnel that points
to `http://127.0.0.1:8765`. Put its token in `tunnel_token`, your hostname in `public_url`
(e.g. `https://ai.example.com`), and set `tunnel_mode` to `named`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Control panel says *"already running"* | Another copy is open. Look in the taskbar, or end `pythonw.exe` in Task Manager |
| LLM shows `● offline` | Start llama.cpp / Ollama / LM Studio, check the URL, click *Refresh models* |
| No QR / no Public URL | Check your internet. The log tells you more, and so does `server/data/cloudflared.log` |
| App says *"Invalid token"* | Re-scan the QR (the token changed, e.g. after *New token*) |
| App says *"Server/tunnel offline"* | The server was restarted: re-pair with the new QR |
| AI doesn't use tools | Use a function-calling model, and start llama.cpp with `--jinja` |
| Startup error mentioning `config.json` | Fix the typo, or delete `server/config.json` (it is recreated) |
| Context / speed numbers don't show | They come from llama.cpp. Other backends may not report the context size |
| Charts don't appear | The AI must save the image to a file (`plt.savefig("chart.png")`), not `plt.show()` |

---

## Security

- Every request needs the **256-bit access token**. 10 wrong attempts lock that IP out for 10 minutes.
- The server listens on **127.0.0.1 only**. The internet reaches it only through the encrypted Cloudflare tunnel.
- The pairing page (`/pair`) only works on the PC itself, never through the tunnel, and only when it's addressed
  as `127.0.0.1`/`localhost`. That blocks "DNS rebinding" attacks from malicious websites.
- Web pages fetched by the AI can't reach your PC or local network (localhost / LAN addresses are blocked).
- The phone stores the URL and token **encrypted** (Android Keystore) and excludes them from backups.
- Code execution and file writes requested by the AI need **your approval** on the phone.
- ⚠️ **Whoever has the token controls your PC.** Keep the QR private, and press **New token** if it leaks.

---

## Build from source

**Server:** plain Python, no build step. `server/bridge/` holds the FastAPI app (`app.py`), tools (`tools.py`),
Cloudflare tunnel (`tunnel.py`) and storage (`db.py`). `server/gui.py` is the control panel.

**Android app** (Kotlin + Jetpack Compose): open `android/` in Android Studio, or:

```bash
cd android
set JAVA_HOME=C:\Program Files\Android\Android Studio\jbr
gradlew assembleRelease
```

The APK is written to `android/app/build/outputs/apk/release/`. If Gradle fails with
*"Unable to establish loopback connection"*, first run `set JAVA_TOOL_OPTIONS=-Djdk.net.unixdomain.tmpdir=C:\gtmp`.

### Project structure

```
LocalAI-Bridge/
├── Start-Server.bat            ← double-click to run (control panel)
├── Start-Server-Console.bat    ← same, console mode
├── release/LocalAI-Bridge.apk  ← ready-to-install Android app
├── server/
│   ├── gui.py                  ← Windows control panel
│   ├── main.py                 ← console launcher
│   ├── requirements.txt
│   └── bridge/                 ← API server, tools, tunnel, database
├── android/                    ← Android app source (Kotlin / Compose)
└── docs/images/                ← screenshots
```
