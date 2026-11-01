# Extension status

This change builds on the user's original Multicombot-App commit, not a replacement application.

Preserved: existing signup/login/sign-out code, Supabase client, company creation form and state, company lookup, authentication styles, dependency choices, assets, FastAPI root and health behavior. Company creation now goes through the verified-user API instead of a direct browser insert. A nested KnowledgeWorkspace adds document upload, approval, publishing and enquiries. PublicBot adds the customer route. The API router reuses the separately tested document processing and scoped chat implementation.

Implemented: private PDF/DOCX/TXT upload and ingestion, source-aware full-text retrieval, explicit approval, owner-only preview, public bot links, publish/unpublish, cited AI replies, customer enquiry collection, row-level security, database rate limits and Render setup.

Not implemented: appointments, payments, OCR, Excel/CSV, semantic/vector retrieval, staff roles, conversation memory, email enquiry notifications or durable ingestion workers. The existing auth form is retained; this extension does not add password recovery or confirmation resend.

Live Supabase migration, AI provider access and Render deployment must be validated with the user's settings. The migration preserves companies and deliberately moves writes to the authenticated backend. Never commit actual environment files. Read ACCEPTANCE.md before presenting or onboarding clients.

## Checks on this extension

- Original React/TypeScript dependency tree retained; frontend production build and ESLint pass.
- 19 backend tests pass using the extended original FastAPI app and mocked database/AI calls.
- 11 embedded PostgreSQL checks pass for policies, scoped retrieval, approval revocation, repeatable migration and rate limits.
- Live AI replies, real Supabase integration, actual email delivery, mobile UI and Render hosting still need connected-environment acceptance testing.

Dependency audit: runtime frontend dependencies have no reported vulnerabilities. The inherited ESLint development dependency tree reports 12 moderate entries rooted in minimatch; a breaking forced downgrade was not applied. Review/update the development toolchain separately.
