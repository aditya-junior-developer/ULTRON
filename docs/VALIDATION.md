# Validation report

Executed in the Linux cloud workspace on 2026-10-09. This records development
validation, not a completed Windows release or live integration certification.

| Check | Result |
| --- | --- |
| Python agent tests, including real process lifecycle | 37 passed |
| Ruff static checks | Passed |
| React UI tests | 3 passed |
| Worker tests with mocked external transport | 10 passed |
| TypeScript checks across workspaces | Passed |
| React production and Electron main/preload builds | Passed |
| Worker Wrangler dry-run build | Passed; no deployment |
| PostgreSQL-compatible PGlite migration/RLS/quota/scheduler test | Passed |
| Browser end-to-end against real Python agent and Chromium | Passed |
| Native Electron headless Linux launch | Failed with SIGSEGV before application validation |
| Frozen Python dependencies, Linux automation/voice extras | Installed |
| Python 3.14 Windows dependency resolution | Passed; Windows imports not tested |

The browser smoke test exercises authenticated connection, memory persistence,
sensitive file-write approval, unchanged files before approval, actual write and
snapshot after approval, mobile layout, and emergency stop. Screenshots are
generated under ignored `artifacts/`. It does not validate native Windows IPC,
microphone, speakers, OS automation, or executable packaging.

After updating Electron, Vite, Vitest and packaging dependencies, the production
dependency audit reports zero vulnerabilities. The full npm audit still reports
eight moderate advisories in the build-tool dependency chain involving
`sprintf-js`/`roarr`/`global-agent`; no upstream fixed `sprintf-js` version was
available at validation. These remain a release review item.

## Remaining release gates

- Run `scripts/Setup-Windows.ps1` and `scripts/Start-ULTRON.ps1` on Windows 11;
  then run the native Electron smoke test and `scripts/Build-Windows.ps1`.
- Verify installed Qwen3 inference, Gemini functionality/free model quotas,
  downloaded speech and wake models, microphone/speaker behavior, and Windows
  automation with explicitly approved test folders/actions.
- Verify Google OAuth and selected APIs using the private desktop client file.
- Review and separately approve Supabase migrations and Cloudflare deployment
  before verifying hosted authentication, RLS, device revocation and sync.
- Address incomplete capabilities listed in [FEATURES.md](FEATURES.md), including
  voice interruption/AEC, live meeting participation, remote notifications,
  large-history sync pagination, and future multi-Google-account support.

No paid infrastructure, paid AI fallback, real calls, database migration, cloud
deployment, GitHub workflow dispatch, repository push, or live Google action was
performed. Provider tests use mocks unless explicitly identified above as real.
The environment lacks the user's credentials, speech models and Windows hardware;
their readiness remains user-reported until verified there.
