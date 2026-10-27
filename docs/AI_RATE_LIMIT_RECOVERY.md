# AI provider rate limits

The reported Groq error was a **tokens-per-day** limit: 199,868 of 200,000 tokens had been used, leaving 132 tokens for a request requiring 2,664. Groq requested a wait of 18 minutes 13.824 seconds. This is not an invalid-key error or a failed slide upload.

Groq's organization allowance is shared by its keys. Replacing a key within the same organization does not reset it. The wait in this error is for enough capacity to serve that request; it does not promise a full daily allowance reset. See [Groq rate limits](https://console.groq.com/docs/rate-limits).

## Recovery behavior

- HTTP 429 starts a cooldown for that configured provider/model. Emby honors `Retry-After` seconds or an HTTP date, with Groq's textual duration as a fallback.
- Configured alternative models/providers are tried immediately. Emby does not repeatedly call an exhausted model or sleep for an entire quota window inside a web request.
- When question generation cannot proceed, saved questions remain in the bank. The job saves `next_attempt_at` in PostgreSQL and releases its lease. Capacity waits do not consume the bounded worker-failure retry budget.
- The existing periodic recovery task resumes eligible jobs. Django's cache also suppresses repeated requests during cooldown; without a shared cache backend this suppression is local to each process. The question-job deadline remains durable across processes and restarts.
- Image indexing uses the same durable cooldown and keeps successfully read pages. Quota waits do not count as failed-document attempts, and refresh/manual retry cannot bypass an active cooldown.
- Slide pages remain readable while AI generation waits. These changes do not increase the provider's quota or guarantee that another provider has capacity.

## Render configuration

The code reads `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and optional `LLM_BACKUP_1_*` through `LLM_BACKUP_3_*` settings. After changing credentials, restart/redeploy every process using them. The repository's current Render blueprint runs Django, Celery and Beat together, so redeploying that combined service refreshes all three. Independently deployed workers need their own updated environment and restart.

Deploy the code changes to activate the new cooldown handling. Existing credentials and subscription plans were not changed by this fix.
