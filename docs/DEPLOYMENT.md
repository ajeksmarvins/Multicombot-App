# Deployment: one Render service

## Before creating the service

1. Run `supabase/001_core.sql` in the existing Multicombot Supabase project.
2. Configure your own AI provider key. Verify that the selected model is available and that the account has enough quota.
3. Use this build branch while testing. Review and merge the pull request when ready; do not automatically merge untested deployments.

## Render settings

Create a new Web Service from `ajeksmarvins/Multicombot-App`, selecting `feature/document-knowledge` (or `main` after merging). `render.yaml` provides a Blueprint alternative; review Render's plan and costs before creating services.

Runtime: Python. Root directory: repository root.

Build command:

```sh
pip install -r backend/requirements.lock.txt && npm ci --prefix frontend && npm run build --prefix frontend
```

Start command:

```sh
cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='127.0.0.1'
```

Health check: `/health`.

Set these environment variables in Render (never commit real values):

- `PYTHON_VERSION=3.13.3`
- `NODE_VERSION=22.14.0`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `VITE_SUPABASE_URL` (same project URL)
- `VITE_SUPABASE_PUBLISHABLE_KEY` (public/publishable or legacy anon)
- `LLM_API_KEY`
- `LLM_BASE_URL=https://api.groq.com/openai/v1`
- `LLM_MODEL=openai/gpt-oss-120b`
- `RATE_LIMIT_SECRET` (random 32+ characters)
- `BOT_DAILY_LIMIT=100`

Leave `VITE_API_URL` empty. Both frontend and backend use the same domain. Vite variables are embedded during the build: changing them requires rebuilding. Server-only keys must not have the `VITE_` prefix.

If the hosting environment does not supply Node, configure its supported Node installation or use a container build. This blueprint's build must be tested in the user's actual Render account; it has not been deployed by this code change.

After Render gives you `https://YOUR-SERVICE.onrender.com`:

1. Set that exact HTTPS origin as Supabase Auth Site URL.
2. Add that origin and `https://YOUR-SERVICE.onrender.com/**` to allowed redirects. Retain local redirects for development if needed.
3. Open `/health` and the homepage, sign in, upload and approve the sample, then publish.
4. Open the bot link from a phone and incognito browser.
5. Set up real SMTP if signup or reset email is restricted by Supabase's development email limits.
6. Verify proxy IP handling. Uvicorn trusts only loopback in this configuration. Do not set `--forwarded-allow-ips='*'` unless the service is protected from direct access and the proxy sanitizes forwarding headers. With an untrusted remote proxy, all visitors may share an IP-based limiter; the global bot cap still works.

## Recovery

A killed worker during synchronous ingestion can leave a file in `processing`. Verify no ingestion request is still active before changing it. In Supabase SQL Editor (operator only), recover **one specific file**, not every processing file:

```sql
update public.documents
set status = 'failed', is_approved = false,
    error_message = 'Processing interrupted. Retry this document.'
where id = 'PASTE_DOCUMENT_UUID' and status = 'processing';
```

The owner can then use Retry in the document workspace. Success replaces all chunks atomically and resets approval to false. Failed files never enter public retrieval.

Deletion disables approval first. If storage deletion fails, retry deleting the now-unapproved record. If a process crashes after file upload but before metadata creation, an unreferenced private object can remain; periodically reconcile bucket objects against `documents.storage_path` before long-term production use.

## Operations before external clients

Configure database/storage backups, error monitoring with secret/PII redaction, provider spending controls, a privacy notice with retention periods, customer deletion procedures, isolated ingestion workers and abuse protection. Test with two separate company owners and real documents. Do not describe this as a fully hardened production SaaS solely because it deploys.

The customer's browser connects directly to Supabase for authentication; company operations go through FastAPI. Customers cannot download the private stored originals through a public object URL. Approved excerpts can still be quoted by the bot.
