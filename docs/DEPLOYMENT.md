# Deployment preparation — approval required

No commands in this document have been used to deploy ULTRON or change your Supabase project.

## Supabase

1. Review `supabase/migrations/001_initial.sql`. It creates the ULTRON tables, owner RLS,
   protected quota counters and a service-role-only atomic reminder scheduler.
2. Back up existing project data. Inspect existing tables and naming conflicts. This
   initial migration intentionally fails rather than silently replacing existing tables.
3. Obtain explicit approval before applying the migration. Its isolated database test
   passed; that does not establish compatibility with an existing live schema.
4. Configure authentication for the single V1 user. Disable public signups if unnecessary.
   The UI email-code flow uses `shouldCreateUser:false`; create/authorize the user first.
   Set the Supabase email template to display `{{ .Token }}` for code entry. Verify mail
   delivery and its free-service limits.
5. Keep the anon/publishable key distinct from the service-role secret. Test both user
   ownership isolation and rejected anonymous requests against the actual project.

## Cloudflare Worker

The existing application uses `npx wrangler deploy`. The root `wrangler.jsonc` supplies
its Worker entry point and web assets. A build is required before deploy:

```text
Root directory: /
Build command: npm ci && npm run build
Deploy command: npx wrangler deploy
```

Review this configuration in Cloudflare after explicit deployment approval; changing it
now could cause an automatic deployment. The repository has not been pushed by this task.

Set non-secret Worker variables: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and an exact
`ALLOWED_ORIGIN` if serving the client on another origin. Same-origin web requests work
without a cross-origin allowlist. Configure `SUPABASE_SERVICE_ROLE_KEY` as a Worker secret
only if scheduled reminders are needed. Its scope is server-side scheduling.

For optional cloud Gemini, securely configure `GEMINI_API_KEY`, an actually verified
`GEMINI_MODEL`, `GEMINI_FREE_TIER_CONFIRMED=true`, and a bounded `MAX_DAILY_AI_REQUESTS`
(default 20, maximum 100). Keep provider billing disabled. With these unset, cloud chat
reports that it is unconfigured rather than pretending to work.

Run `npm run build -w @ultron/cloud-worker` for the dry run. Obtain separate explicit
deployment approval before `npx wrangler deploy`. Test authentication, cross-user RLS,
chat failures, scheduling and web assets on the actual deployment before claiming success.

Cron checks occur every 15 minutes and are event-driven. In-app reminders are stored
when the desktop is off; push/email delivery is not implemented. Cloud Google workflows
need a Web OAuth client, encrypted server token storage and a separately authorized
implementation; no Desktop OAuth tokens are uploaded.

## Windows distribution

Run the documented build on Windows. Validate the installer and portable package on a
clean Windows account, including bundled imports, speech models, Chrome, startup,
shutdown, microphone permissions and credential-manager storage. Verify trusted
checksums and licence notices. Unsigned installers may produce Windows reputation warnings.

Automated publishing and automatic self-generated update installation are disabled.
Manual-only CI avoids unexpected recurring usage. No code here authorizes a paid overage.
