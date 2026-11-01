-- Run in the Multicombot project's SQL Editor. Preserves existing company records.
begin;
create table if not exists public.companies (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null unique references auth.users(id) on delete cascade,
 name text not null check (char_length(trim(name)) between 2 and 100),
 slug text not null unique default gen_random_uuid()::text,
 bot_name text not null default 'Company Assistant',
 welcome_message text not null default 'Hello! What would you like to know about our company?',
 is_published boolean not null default false,
 created_at timestamptz not null default now()
);
create table if not exists public.documents (
 id uuid primary key default gen_random_uuid(),
 company_id uuid not null references public.companies(id) on delete cascade,
 filename text not null, storage_path text not null unique,
 status text not null default 'uploaded' check(status in ('uploaded','processing','ready','failed')),
 is_approved boolean not null default false,
 error_message text, created_at timestamptz not null default now()
);
create index if not exists documents_company_id_idx on public.documents(company_id);
create table if not exists public.document_chunks (
 id bigint generated always as identity primary key,
 document_id uuid not null references public.documents(id) on delete cascade,
 company_id uuid not null references public.companies(id) on delete cascade,
 page_number integer not null, content text not null,
 search_vector tsvector generated always as (to_tsvector('english', content)) stored
);
create index if not exists chunks_search_idx on public.document_chunks using gin(search_vector);
create index if not exists chunks_company_idx on public.document_chunks(company_id);
create table if not exists public.enquiries (
 id uuid primary key default gen_random_uuid(),
 company_id uuid not null references public.companies(id) on delete cascade,
 name text not null, email text not null, message text not null,
 created_at timestamptz not null default now()
);
create index if not exists enquiries_company_idx on public.enquiries(company_id);
create table if not exists public.rate_limits (
 key text primary key, hits integer not null, expires_at timestamptz not null
);
alter table public.companies enable row level security;
alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;
alter table public.enquiries enable row level security;
alter table public.rate_limits enable row level security;
-- Replace previous tutorial policies, including broader write grants.
drop policy if exists "Owners can view their company" on public.companies;
drop policy if exists "Owners can create their company" on public.companies;
drop policy if exists "Owners can update their company" on public.companies;
drop policy if exists "Owners manage their company documents" on public.documents;
drop policy if exists company_owner on public.companies;
drop policy if exists document_owner on public.documents;
drop policy if exists enquiry_owner on public.enquiries;
revoke all on public.companies, public.documents, public.document_chunks, public.enquiries, public.rate_limits from anon, authenticated;
-- All writes go through the authenticated API. Browsers may read only their own records.
grant select on public.companies, public.documents, public.enquiries to authenticated;
grant all on public.companies, public.documents, public.document_chunks, public.enquiries, public.rate_limits to service_role;
grant usage, select on sequence public.document_chunks_id_seq to service_role;
create policy company_owner on public.companies for select to authenticated
 using(owner_id = (select auth.uid()));
create policy document_owner on public.documents for select to authenticated
 using(exists(select 1 from public.companies c where c.id = company_id and c.owner_id = (select auth.uid())));
create policy enquiry_owner on public.enquiries for select to authenticated
 using(exists(select 1 from public.companies c where c.id = company_id and c.owner_id = (select auth.uid())));

create or replace function public.ingest_chunks(p_document uuid, p_company uuid, p_chunks jsonb)
returns void language plpgsql set search_path = public as $$
begin
 perform 1 from documents where id = p_document and company_id = p_company and status = 'processing' for update;
 if not found then raise exception 'Document is not processing'; end if;
 if jsonb_array_length(p_chunks) < 1 or jsonb_array_length(p_chunks) > 400 then
   raise exception 'Invalid chunk count';
 end if;
 delete from document_chunks where document_id = p_document and company_id = p_company;
 insert into document_chunks(document_id, company_id, page_number, content)
 select p_document, p_company, (v->>'page_number')::int, v->>'content'
 from jsonb_array_elements(p_chunks) v;
 update documents set status = 'ready', error_message = null, is_approved = false
 where id = p_document and company_id = p_company;
end; $$;

create or replace function public.search_knowledge(p_company uuid, p_question text)
returns table(content text, filename text, page_number integer, document_id uuid, rank real)
language sql stable set search_path = public as $$
 select ch.content, d.filename, ch.page_number, d.id,
 ts_rank_cd(ch.search_vector, websearch_to_tsquery('english', regexp_replace(trim(left(p_question,1000)), '\s+', ' OR ', 'g'))) as rank
 from document_chunks ch join documents d on d.id = ch.document_id and d.company_id = ch.company_id
 where ch.company_id = p_company and d.company_id = p_company
 and d.status = 'ready' and d.is_approved = true
 and ch.search_vector @@ websearch_to_tsquery('english', regexp_replace(trim(left(p_question,1000)), '\s+', ' OR ', 'g'))
 order by rank desc, ch.id asc limit 5;
$$;

-- Atomic limiter, shared by all API workers; key contains an HMAC, not a raw IP address.
create or replace function public.consume_limit(p_key text, p_limit int, p_seconds int)
returns boolean language plpgsql set search_path = public as $$
declare n int;
begin
 delete from rate_limits where expires_at < now();
 insert into rate_limits(key,hits,expires_at) values(p_key,1,now()+make_interval(secs=>p_seconds))
 on conflict(key) do update set hits = rate_limits.hits + 1 returning hits into n;
 return n <= p_limit;
end; $$;
revoke all on function public.ingest_chunks(uuid,uuid,jsonb) from public, anon, authenticated;
revoke all on function public.search_knowledge(uuid,text) from public, anon, authenticated;
revoke all on function public.consume_limit(text,int,int) from public, anon, authenticated;
grant execute on function public.ingest_chunks(uuid,uuid,jsonb) to service_role;
grant execute on function public.search_knowledge(uuid,text) to service_role;
grant execute on function public.consume_limit(text,int,int) to service_role;
-- Private storage. No anonymous or authenticated object policies are created.
insert into storage.buckets(id,name,public,file_size_limit)
values('company-documents','company-documents',false,10485760)
on conflict(id) do update set public = false, file_size_limit = 10485760;
commit;
