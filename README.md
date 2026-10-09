# ULTRON

ULTRON is an integrated personal assistant workspace: an Electron/React desktop,
an authenticated Python local agent, SQLite memory, optional local speech and AI,
Google OAuth integrations, and a Cloudflare/Supabase cloud backend.

**This is a development implementation, not a verified production V1 release.**
Portable tests and builds are recorded in [the validation report](docs/VALIDATION.md).
Windows hardware checks, live provider checks, account integrations and packaging
remain separate release gates. No cloud deployment or Supabase migration has been run.

## Windows development

Prerequisites: Windows 11 x64, Python 3.12–3.14, Node 24, Git, and Chrome. Keep Gemini
billing disabled and GitHub paid overages disabled. This project never enables billing.

For one-command setup and launch, run `scripts\Setup-Windows.ps1` and then
`scripts\Start-ULTRON.ps1` in PowerShell. To create executables, run
`scripts\Build-Windows.ps1`. These scripts are prepared but unrun on Windows.

```powershell
python -m pip install uv==0.12.24
uv sync --frozen --all-extras
npm ci
npx --no install-electron --no
npm run build
$env:ULTRON_PYTHON = (Resolve-Path .venv\Scripts\python.exe).Path
npm run desktop
```

The desktop starts its own loopback agent, chooses a free port, and passes an ephemeral
session token through isolated IPC. No manual token copying is needed in Electron.
The window closing stops the agent; it does not silently continue listening.

For browser-based local development, start the agent and web UI in separate terminals:

```powershell
uv run --frozen --extra dev ultron-agent
npm run dev
```

The agent prints a local session token for this manual workflow. Enter it only in the
local connection form; do not share it or place it in a URL. The web UI keeps tokens in
memory. `.env.example` documents environment variables; `.env` is **not automatically
loaded**, and real secrets must not be committed. Prefer the Settings credential form
and Windows Credential Manager.

## Initial configuration

1. Confirm `ollama list` includes `qwen3:4b`, and test it with `ollama run qwen3:4b`.
   ULTRON queries the local service; it does not install Ollama or download an LLM.
2. Leave permissions disabled until needed. Approve specific project folders rather
   than a drive or home directory. Sensitive actions show exact arguments and expire
   after five minutes if unconfirmed.
3. For Gemini, store the key securely, confirm Free tier/billing disabled, enable cloud
   AI, then discover actual model IDs. Pick a model with verified free access. Local
   Gemini requests are capped at 20/day; a cloud Worker has its own bounded cap.
4. For voice, download a licensed faster-whisper model directory and Piper ONNX voice
   with its matching `.onnx.json`. Set their local paths. Optional wake-word listening
   requires a compatible downloaded ONNX wake model; “Ultron” recognition is not
   supplied or verified. Model downloads are not automatic.
5. Select your private Desktop Google OAuth JSON path and only the scope groups needed,
   save settings, then authorize. Tokens are held in the OS credential store.
6. For cloud access, first review [deployment instructions](docs/DEPLOYMENT.md).

## Checks

```powershell
uv run --frozen --extra dev pytest -q
uv run --frozen --extra dev ruff check services/local-agent tests scripts
npm run typecheck
npm test
node --test tests/database.test.mjs
npm run build
npm run build -w @ultron/cloud-worker
```

The Worker build is a **dry run**, not deployment. For the browser smoke test, install
the automation extra and Chromium (`uv run --extra automation playwright install chromium`)
then run `uv run --extra automation python tests/e2e/run.py`. It requires an available
port 5173. Linux can use `ULTRON_TEST_BROWSER=/usr/bin/chromium`.

## Windows release preparation

```powershell
uv run --frozen --all-extras python scripts/build-agent.py
npm run package:win
python scripts/release-manifest.py
```

Builds are unsigned unless a signing certificate is separately provided. The checksum
manifest detects changed bytes only when received through a trusted channel; it is not
a publisher signature. Packaging has not been tested on this Linux machine. Review
third-party licence obligations, including Piper and individual voice models, before
distributing binaries.

GitHub workflows are manual-only, bounded in duration, and never deploy or apply schemas.
Check remaining included Actions capacity before dispatch; a workflow cannot configure
your account billing policy. Local Windows builds are the fallback.

See [architecture](docs/ARCHITECTURE.md), [security](docs/SECURITY.md),
[feature status](docs/FEATURES.md), and [deployment](docs/DEPLOYMENT.md).
