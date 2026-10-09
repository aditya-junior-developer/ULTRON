# Integrated architecture

`apps/desktop` owns the Electron process and launches `ultron-agent`. Its renderer uses
`apps/web`, which also runs as a responsive cloud client. Context isolation, sandboxing,
disabled Node integration, a strict production CSP, denied renderer permissions, and a
narrow preload bridge isolate the UI from OS commands.

`services/local-agent/ultron` contains the FastAPI boundary, SQLite store, credential
vault, AI router, task engine, registered actions, Google adapter, cloud synchronizer,
and optional voice engine. Opt-in learning aggregates approved app/command frequencies. The agent binds only to loopback and requires a constant-time
checked bearer token. Origin checks are complemented by host validation; the API must
not be exposed on a LAN or the Internet.

## AI and tasks

Automatic routing prefers Ollama, then permitted Gemini and a verified free compatible
endpoint. An explicitly selected cloud provider falls back to Ollama. No paid provider
is enabled by default. Gemini uses header authentication, model discovery and a local
daily cap. Ollama limits context, output, threads and keep-alive time to constrain load.

The model sees only registered JSON-schema tools. It cannot supply shell strings.
The assistant performs at most three model rounds and bounded tool calls per request.
It waits for low-risk outcomes, labels them untrusted, and can choose a recovery step.
Sensitive actions interrupt execution for review; dependent steps are not executed
before approval. After approval, continue the conversation with the recorded result.
Provider calls and tasks have timeouts. No LLM can classify its own requested action as safe.

Development commands are a fixed list, run without a shell in approved folders.
They still execute repository-controlled test/build code and therefore need approval.
Snapshot-backed edits and tests provide a reviewable improvement workflow. There is
no self-installing updater: generated changes must be reviewed, tested and packaged
before a user installs an update. Fully isolated self-improvement sandboxes remain a
release limitation; the development-command action is not an OS sandbox.

## Voice

The optional CPU pipeline is 16 kHz microphone capture, amplitude VAD, optional ONNX
wake-word activation, int8 faster-whisper transcription, AI response, and Piper output.
English/Hindi/automatic language modes are selectable; Hinglish quality is empirical.
Model files are user-provided. Microphone data and screen captures are not archived.
Current playback is half-duplex to avoid feedback. UI interruption is implemented;
full voice barge-in and acoustic echo cancellation are not implemented.

## Storage and cloud

SQLite holds explicit memories, conversations, task results, settings, schedules,
events and deletion tombstones. FTS5 provides memory search. Conversations and memories
can synchronize manually after a sensitive-action approval. Synchronization uses UUIDs,
memory timestamps and deletion tombstones. Batches are bounded at 100 records per entity;
large histories require paginated synchronization before claiming full archival sync.
Conflicting memory timestamps use last-write-wins and assume reasonably synchronized
device clocks. The protocol is not end-to-end encrypted; HTTPS and provider storage
security protect transport and storage.

`services/cloud-worker` is a TypeScript Worker with static web assets. Every protected
request validates its Supabase session server-side. Database calls use the user's token
and RLS, not a service-role key. The optional scheduler is service-role-only and atomically
claims at most 100 due reminders every 15 minutes. Cloud tasks are in-app reminders;
arbitrary webhooks, shells, calls and messages do not run unattended.

Schema proposals cover profiles, settings, devices, conversations/messages, memories,
tasks, schedules, activity, integration metadata, approvals, sync tombstones and usage.
Client secrets and Google tokens are not put in those metadata tables.

The cloud provides remote text chat, memory and task monitoring. Local Windows control,
screen/microphone access and Ollama require a connected running desktop. Free-tier limits,
pausing and account policies prevent an uninterrupted availability guarantee.

## Google and future accounts

The V1 desktop OAuth adapter connects the user's test account. Scopes are grouped and
selected explicitly. Gmail supports listing/reading, drafts and approval-gated sending;
Calendar supports listing and event creation; Drive uses `drive.file` for approved files
and export backups; People supports read-only contacts; Meet lists accessible recording
and transcript resources without joining or recording a meeting.

Cloud user isolation is already based on Supabase user UUIDs. Multiple simultaneous
Google accounts per desktop user and a remote Web OAuth token service are future
extensions; V1 stores one desktop Google connection. Desktop OAuth tokens are not
silently uploaded or treated as usable cloud credentials.
