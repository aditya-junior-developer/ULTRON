# Security and budget boundaries

All microphone, screen, desktop automation, AI tool execution, cloud AI and synchronization
permissions start disabled. Camera capture is rejected because it is not implemented. Opt-in learning stores only
frequencies of approved app openings and development checks, with a deletion control. The stop control cancels queued/running work,
disables schedules, stops listening and interrupts speech. Cancellation cannot retract
a message already sent or guarantee cancellation of a synchronous external HTTP request.

Sensitive task arguments are immutable after submission. Approval applies to the displayed
task once, expires after five minutes, and is never inferred from timeout. Restart cancels
pending approvals and marks running tasks interrupted rather than retransmitting them.
Emails require an explicitly displayed recipient, subject and body. Browser clicks may
submit data and are sensitive; no browser passwords are extracted.

Approved file paths are resolved before use and reject traversal, symlink escape and
credential/Git metadata directories. Existing files are snapshotted before edits/deletion.
Whole-directory deletion, arbitrary shell commands, software installation and security
configuration changes are not exposed as model tools. OS symlink races and hostile code
in an approved repository require a true OS sandbox for stronger isolation; do not approve
untrusted repositories for command execution.

Browser automation uses its own visible persistent profile. This profile may hold
website session cookies on the local device. Sign out and delete the profile when
revoking access. It never reuses the user's primary Chrome profile. Private literal-IP
destinations, insecure URLs and embedded credentials are rejected, but DNS rebinding
requires additional network isolation before hostile-site automation is production-ready.

Credentials are stored in an OS keyring or explicitly injected process variables. There
is no plaintext credential-file fallback. A Linux machine without a secure keyring cannot
persist secrets through the UI. Logs omit provider request bodies and API-key-bearing URLs.
SQLite, snapshots and the isolated browser profile contain private data and need normal
OS account/disk protection; they are not encrypted by this application. Screen PNGs live
only in memory unless a user separately saves them. Task results and approved file reads
can contain sensitive text; review retention and export behavior.

Memory deletion tombstones propagate on approved sync. Local erasure leaves tombstones
to prevent re-upload on the next sync. Recovery snapshots and Google Drive backups are
separate copies and require separate deletion. Cloud erasure and desktop erasure are
separate operations; a future complete deletion protocol must address all registered
devices. Retention runs at startup locally; continuous cloud retention enforcement is
not yet implemented. Manual memory is retained until explicitly deleted.

Supabase RLS isolates each user's records. The service-role key is reserved for the
server-side scheduler and must never appear in the web bundle. Device requests require a random device secret, stored as a hash server-side. Revocation
blocks that device on subsequent Worker requests. Also revoke Supabase sessions if a user
session is compromised, because a valid user session can enroll another device. Role administration
and advanced device policy need additional work before multi-user production deployment.

## ₹0 policy

Gemini requires explicit free-tier/billing-disabled confirmation plus cloud permission.
Cloud Gemini is disabled in the committed configuration. Models and free quotas must be
verified on the actual account; listing a model is not proof of free access. The application
has local/cloud daily caps and no paid fallback, but cannot independently turn off provider
billing. Keep account-level billing disabled. Custom endpoints require no-cost confirmation.

No telephone provider is activated. GitHub Actions are manual-only; check allowance and
disable paid overages. Cloudflare/Supabase deployment requires separate approval and a
review of current free-tier eligibility. No uptime guarantees are made.

Dependency scanning and tests reduce risk but are not a security audit. Publication,
database migrations, sending messages and installation of generated updates remain
separate user-authorized actions.
