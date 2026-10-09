# V1 feature status

“Implemented” means code exists and is integrated. It does not establish successful
operation with hardware or external accounts. See VALIDATION.md for executed checks.

| Area | Implementation | Remaining verification or limitation |
|---|---|---|
| Desktop/web interface | Responsive React UI, animated orb, chat, status, models, tasks, settings and activity | Windows runtime and installer acceptance |
| AI providers | Ollama, Gemini, configurable OpenAI-compatible endpoint | Real models, credentials, quotas and response quality |
| Provider failover | Local-first/capability checks, permitted fallback, daily Gemini cap, actionable errors | Live outage tests |
| Task planning | Bounded native tool-calling rounds, actual low-risk outcomes, approval pause | Model-specific tool reliability and long tasks |
| Conversation context | SQLite history and explicit searchable memory | Long-history summarization not implemented |
| Local AI | Ollama service requests with CPU/context/output limits | Qwen3 download and inference on the user's laptop |
| Speech recognition | CPU int8 faster-whisper, automatic/English/Hindi/Hinglish modes | Local model files and multilingual audio tests |
| Speech synthesis | Piper local playback, speed/volume control | Licensed male English/Hindi voice files and quality tests; pitch unsupported |
| Wake word | Optional Windows openWakeWord ONNX pipeline | Compatible custom Ultron model not supplied; false-wake testing |
| Interruptions | Immediate UI stop; silent-command recognition while listening | Voice barge-in during playback and acoustic echo cancellation not implemented |
| Windows control | App/window control, volume, supported brightness, approved folders | Native Windows integration tests |
| Files/coding | Bounded search, approved reads, snapshot-backed writes/deletes, fixed development checks | OS sandboxing for untrusted project execution not implemented |
| Browser | Isolated Chrome profile, navigation/tabs, extraction, forms and approved downloads | Headed Windows tests, hostile-site network isolation |
| Screen understanding | One-time approved in-memory PNG attachment, verified local vision capability or permitted cloud routing | Live vision-model check; continuous screen monitoring not implemented |
| Scheduling | One-time/recurring local reminders, restricted recurring read tasks | Windows notification behavior |
| Notifications | Desktop native reminder notifications; in-app cloud reminders | Remote push/email delivery not implemented |
| Proactive learning | Opt-in app/command frequencies, failure/configuration suggestions, deletion | No passive screen observation or broad behavioral inference |
| Local memory | SQLite FTS search, edits, export, retention and deletion | Disk encryption is supplied by the OS, not the app |
| Cloud sync | Bounded record merge, corrections, deletion tombstones | Live Supabase tests; large-history pagination and complete multi-device erasure need more work |
| Supabase/auth | Proposed owner-RLS schema, email-code auth, server-validated sessions | Migration approval, live schema/configuration and email delivery |
| Device management | Registration, per-device secret hashing and request enforcement, revocation endpoints | Live account/session revocation tests; enrollments still require valid user session |
| Cloudflare | Worker entry point, static assets, cron, remote chat, memory and tasks | Separate approval, secrets, migration and actual deployment |
| Gmail | List/read messages, drafts, approval-gated sending | Desktop OAuth, scope grants and live requests |
| Calendar | List and create events | Google authorization; invitation and Meet creation extensions |
| Drive | App-authorized files and approval-gated export backup | Google authorization; additional formats/download operations |
| People | Read-only contacts | Google authorization |
| Meet | List authorized recording/transcript resources | Account eligibility; joining, live media capture and summarization pipeline not implemented |
| Calling | Adapter contract with explicit zero-budget denial | No verified free PSTN service; no outgoing/incoming telephone calls |
| Code/self-improvement | Registered file edits, snapshots, fixed tests, manual release/checksum preparation | No automatic installation; isolated self-improvement sandbox and signed updater not implemented |
| Packaging/CI | PyInstaller backend, NSIS installer, portable executable targets, manual bounded CI | Windows package build and clean-machine testing unrun |
| Future platforms/users | Shared responsive client, per-user cloud ownership and adapter boundaries | Native mobile clients, multiple simultaneous desktop Google accounts and Web Google OAuth not implemented |

No billing, paid calling, external messages, migrations, deployments, pushes or releases
were authorized by ordinary local development tests. Missing functionality is not
represented as an operational integration.
