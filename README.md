# Multicombot

**Your company’s knowledge. Your audience’s answers.**

A deployable product pilot for multiple companies, built with React + TypeScript, FastAPI, Supabase Auth, private Supabase Storage, PostgreSQL full-text retrieval, and an OpenAI-compatible chat provider (Groq by default).

## Built on your existing application

This change extends the original `App.tsx`, `CompanySetup.tsx`, Supabase client and FastAPI `main.py`. Your existing authentication form, styles, React/Vite dependencies and source assets are retained. The document workspace is a new component embedded in the existing company screen; public chat uses a separate route. Backend knowledge endpoints live in `backend/knowledge.py` and are included by your original FastAPI app.

## What is implemented

- Existing email signup, login and sign-out retained. Confirmation resend and password reset are not added in this extension.
- One owner and one company assistant per account. Existing tutorial companies are retained.
- Private PDF / DOCX / UTF-8 TXT uploads, bounded extraction, page-aware chunks, processing status and retry.
- Explicit owner approval. Only ready, approved documents enter answers.
- Owner-only preview, publishing/unpublishing and a unique public chatbot link.
- Grounded AI responses with numbered source excerpts and a missing-information fallback.
- Customer enquiry collection, owner inbox and deletion.
- Server-side user verification, company-scoped data access, database row-level security and shared database rate limits.
- Responsive dashboard and customer chat. Production build and a single-service Render configuration.

**Not implemented:** appointment scheduling, payments, paid-content entitlements, Excel/CSV, OCR, staff roles, semantic/vector search, multilingual retrieval and conversation memory. These are follow-on work, not working features hidden behind placeholder buttons. This pilot is not certified as production-ready.

## 1. Get the code safely on Windows

Keep the existing laptop folder intact. Open a PowerShell terminal in Documents and clone into a different folder:

```powershell
cd "$env:USERPROFILE\Documents"
git clone -b feature/document-knowledge https://github.com/ajeksmarvins/Multicombot-App.git Multicombot-Review
cd Multicombot-Review
```

After the build branch is merged, new clones can use `main` instead. No `.env` files, uploads, dependencies or API keys are committed.

## 2. Supabase migration

Use your **Multicombot** project, not FarmDtech.

1. Open SQL Editor and run the entire [supabase/001_core.sql](supabase/001_core.sql).
2. This preserves company records and creates/updates the required tables, policies, functions and private `company-documents` bucket. It deliberately replaces the tutorial's direct browser write permissions with API-controlled writes. The updated CompanySetup component creates companies through the API. The earlier local version still writes directly to the database, so update your code before applying the migration.
3. In Authentication → URL Configuration, use `http://localhost:5173` as Site URL and add `http://localhost:5173/**` to allowed redirect URLs.
4. Keep email confirmation enabled. Built-in email sending has provider limits; for real users, configure your own SMTP provider. Open only the newest confirmation/reset email, on the device running the app.

## 3. Backend

From the new repository root:

```powershell
py -3.13 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
Copy-Item backend\.env.example backend\.env
```

Edit `backend/.env` locally:

| Variable | Value |
|---|---|
| `SUPABASE_URL` | Your Multicombot project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend secret/service-role key. Never use a frontend publishable key here. |
| `LLM_API_KEY` | Your Groq key, or the key for your chosen compatible provider |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` for Groq |
| `LLM_MODEL` | `openai/gpt-oss-120b` by default; use an available model in your provider account |
| `RATE_LIMIT_SECRET` | A stable random secret of at least 32 characters |
| `ALLOWED_ORIGINS` | Local frontend origins; already set in the example |
| `BOT_DAILY_LIMIT` | 100 requests per bot per rolling 24-hour allowance by default |

Generate the limiter secret with:

```powershell
py -3.13 -c "import secrets; print(secrets.token_hex(32))"
```

Start the backend:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload --port 8001
```

Your existing `/` and `/health` endpoints are retained. Health: `http://127.0.0.1:8001/health`. API docs: `http://127.0.0.1:8001/docs`.

## 4. Frontend

Open a **second terminal** in the repository root:

```powershell
Copy-Item frontend\.env.example frontend\.env.local
```

Edit `frontend/.env.local`:

```dotenv
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
VITE_API_URL=
```

A legacy `anon` key also works. **Never use `service_role` or `sb_secret_...` in a `VITE_` variable.** Vite variables are public browser configuration, even if stored in a local environment file.

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:5173`. The port is intentionally fixed to match the Supabase redirect. Vite forwards `/api` to port 8001. Leave both terminals running. No CORS changes are needed for the bundled deployment or local Vite proxy.

## 5. Try the core flow

1. Sign in using your existing login screen and owner account. The existing NIVEADA company should load if you used the same Supabase project.
2. In your company workspace, choose a document under Add company knowledge. Try [samples/niveada-guide.txt](samples/niveada-guide.txt), which is labelled as fictional demo content.
3. Wait for `ready`, review the file locally, then check **Approved**.
4. Preview the bot and ask: “What are your opening hours?” or “How long does delivery take?”
5. In your company workspace, click Publish bot → Copy customer link.
6. Open the copied link in a signed-out/incognito browser. Ask a question and expand its source.
7. Ask “Who is the CEO?” (absent from the sample). The bot should decline and offer the enquiry form.
8. Submit an enquiry, then see it in the owner’s Customer enquiries section. It is stored, not emailed.
9. Unapprove the document: subsequent retrievals must stop using it. Unpublish: public bot access must return unavailable.
10. Register a second test company with different documents. Repeat the company isolation checks in [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md).

AI answers send the question and up to five selected approved excerpts to the configured AI provider. Company owners should approve only content they intend to expose to that bot’s audience. Do not upload real confidential data for the product demo.

## 6. Deploy

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). One Render service serves both frontend and API, avoiding separate frontend hosting and cross-origin configuration. Hosting and AI API accounts may incur charges independently of ChatGPT Plus.

## 7. Validation

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

In the frontend folder:

```powershell
npm.cmd run build
npm.cmd audit
```

Database security regression: `cd qa; npm.cmd ci; npm.cmd test` uses embedded PostgreSQL, with simulated Supabase auth/storage schemas. No cloud credentials required. It does not replace testing the migration in the real Supabase project.

See [docs/STATUS.md](docs/STATUS.md) for precisely what was checked and what still needs live validation.

## How retrieval works

Extraction splits text into 1,200-character chunks with 150-character overlap and retains PDF page numbers. PostgreSQL English full-text search ranks matching chunks only within the company’s ready and approved documents. The API passes at most five results to the AI. It accepts only answers containing valid numbered citations; otherwise it uses the fallback. This prevents uncited answers from appearing as sourced, but it does not prove every generated sentence is correct. Check source excerpts and evaluate questions from your actual documents.

This version uses lexical retrieval, not embeddings: synonyms and non-English questions can miss relevant passages. Each question is independent. Follow-up questions should repeat the subject.

## Operational limits

- 10 MB per file, 100 PDF pages, 200,000 extracted characters and 400 chunks per document.
- Pilot UI limit: 30 documents per company, 100 most recent enquiries shown.
- Chat: 10 requests/minute per bot/client IP, plus 100 per bot per rolling day; enquiries: 3/hour per bot/client IP; uploads/retries: 5/minute per company/client IP.
- IP identifiers are HMAC-hashed and counters live in PostgreSQL. The app ignores arbitrary forwarded IP headers; deployment proxy settings must be verified before public use. Clients behind a shared proxy may share limits.
- Processing happens in the upload request. There is no durable job queue; crashed processing may need operator recovery (deployment notes). For larger/hostile workloads, add isolated ingestion workers with CPU/memory/time limits and stronger upload scanning.
- Removing a document revokes its approval before deleting the stored original and database chunks. Requests already in flight may have retrieved the old approved content. Approval changes cannot retract text a customer has already seen.
- Backups, monitoring, privacy/retention policies, real SMTP, robust bot-abuse protection and load testing must be configured before onboarding real clients.

## Official references

- https://supabase.com/docs/guides/database/postgres/row-level-security
- https://supabase.com/docs/guides/storage/security/access-control
- https://supabase.com/docs/guides/auth/redirect-urls
- https://console.groq.com/docs/openai
