import { PGlite } from "@electric-sql/pglite";
import fs from "node:fs";
const db = new PGlite();
await db.exec(`create role anon; create role authenticated; create role service_role bypassrls;
create schema auth; create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
create schema storage; create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint);
grant usage on schema public, auth to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;
`);
const sql = fs.readFileSync(
  new URL("../supabase/001_core.sql", import.meta.url),
  "utf8",
);
await db.exec(sql);
await db.exec(sql); // Migration is repeatable.
const u1 = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  u2 = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const c1 = "11111111-1111-4111-8111-111111111111",
  c2 = "22222222-2222-4222-8222-222222222222";
const d1 = "33333333-3333-4333-8333-333333333333",
  d2 = "44444444-4444-4444-8444-444444444444";
await db.exec(`insert into auth.users values('${u1}'),('${u2}');
insert into companies(id,owner_id,name) values('${c1}','${u1}','Alpha'),('${c2}','${u2}','Beta');
insert into documents(id,company_id,filename,storage_path,status) values('${d1}','${c1}','alpha.txt','alpha','processing'),('${d2}','${c2}','beta.txt','beta','processing');`);
await db.query("select ingest_chunks($1,$2,$3)", [
  d1,
  c1,
  JSON.stringify([
    { page_number: 1, content: "Opening hours are Monday to Friday 9 AM." },
  ]),
]);
await db.query("select ingest_chunks($1,$2,$3)", [
  d2,
  c2,
  JSON.stringify([
    { page_number: 1, content: "Secret Beta opening hours are 11 PM." },
  ]),
]);
function assert(ok, msg) {
  if (!ok) throw new Error(msg);
  console.log("PASS:", msg);
}
assert(
  (
    await db.query("select * from search_knowledge($1,$2)", [
      c1,
      "What are the opening hours?",
    ])
  ).rows.length === 0,
  "Unapproved documents excluded",
);
await db.exec("update documents set is_approved=true");
let rows = (
  await db.query("select * from search_knowledge($1,$2)", [
    c1,
    "What are the opening hours?",
  ])
).rows;
assert(
  rows.length === 1 && rows[0].filename === "alpha.txt",
  "Full-text retrieval returns only target company",
);
await db.exec(`set role authenticated; set request.jwt.claim.sub='${u1}';`);
assert(
  (await db.query("select * from companies")).rows.length === 1,
  "Owner reads only own company",
);
assert(
  (await db.query("select * from documents")).rows.length === 1,
  "Owner reads only own documents",
);
for (const [query, label] of [
  [`select * from document_chunks`, "No direct chunk access"],
  [`select * from search_knowledge('${c2}','hours')`, "No browser RPC bypass"],
  [
    `update documents set is_approved=true`,
    "Approval writes restricted to backend",
  ],
]) {
  let denied = false;
  try {
    await db.exec(query);
  } catch {
    denied = true;
  }
  assert(denied, label);
}
await db.exec("reset role; set role service_role;");
assert(
  (await db.query("select consume_limit('test',1,60) ok")).rows[0].ok,
  "First request allowed",
);
assert(
  !(await db.query("select consume_limit('test',1,60) ok")).rows[0].ok,
  "Second request limited",
);
await db.exec("reset role;");
await db.exec(`update documents set is_approved=false where id='${d1}'`);
assert(
  (
    await db.query("select * from search_knowledge($1,$2)", [
      c1,
      "opening hours",
    ])
  ).rows.length === 0,
  "Revocation takes effect on next retrieval",
);
assert(
  (
    await db.query(
      "select public from storage.buckets where id='company-documents'",
    )
  ).rows[0].public === false,
  "Private storage configured",
);
await db.close();
