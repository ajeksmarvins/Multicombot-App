import hashlib
import hmac
import os
import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from extraction import MAX_BYTES, extract
from services import Store, generate

app = APIRouter()
FALLBACK = 'I could not find that in the approved documents. Please contact the company using the enquiry form.'
DOC_FIELDS = 'id,company_id,filename,status,is_approved,error_message,created_at'


async def limit(store, request, scope, count=20, seconds=60):
    secret = os.getenv('RATE_LIMIT_SECRET', '')
    if len(secret) < 32:
        raise HTTPException(503, 'Platform rate limit settings are missing.')
    # Never trust arbitrary X-Forwarded-For. See deployment notes for proxy settings.
    ip = request.client.host if request.client else 'unknown'
    digest = hmac.new(secret.encode(), ip.encode(), hashlib.sha256).hexdigest()
    allowed = await store.rpc('consume_limit', {'p_key': scope + ':' + digest, 'p_limit': count, 'p_seconds': seconds})
    if not allowed:
        raise HTTPException(429, 'Usage limit reached. Please try again later.')


def store_dependency():
    return Store()


async def owner(request: Request, store: Store = Depends(store_dependency)):
    token = request.headers.get('Authorization', '')
    if not token.startswith('Bearer ') or len(token) > 8192:
        raise HTTPException(401, 'Please sign in.')
    return await store.user(token[7:])


async def own_company(store, user_id):
    rows = await store.rows('companies', owner_id='eq.' + user_id, select='*', limit='1')
    if not rows:
        raise HTTPException(404, 'Create your company first.')
    return rows[0]


async def own_document(store, user_id, document_id):
    company = await own_company(store, user_id)
    rows = await store.rows('documents', id='eq.' + str(document_id), company_id='eq.' + company['id'], select='*', limit='1')
    if not rows:
        raise HTTPException(404, 'Document not found.')
    return company, rows[0]


async def visible_company(store, slug, request, preview=False):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', slug):
        raise HTTPException(404, 'Bot not found.')
    rows = await store.rows('companies', slug='eq.' + slug, select='*', limit='1')
    if not rows:
        raise HTTPException(404, 'Bot not found or not published.')
    company = rows[0]
    if preview:
        user_id = await owner(request, store)
        if company['owner_id'] != user_id:
            raise HTTPException(404, 'Bot not found.')
    elif not company['is_published']:
        raise HTTPException(404, 'Bot not found or not published.')
    return company


class CompanyInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    bot_name: str = Field(min_length=1, max_length=100)
    welcome_message: str = Field(default='Hello! What would you like to know about our company?', max_length=500)


class PublishInput(BaseModel):
    published: bool


class ApprovalInput(BaseModel):
    approved: bool


class ChatInput(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class EnquiryInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    message: str = Field(min_length=5, max_length=2000)
    consent: bool


@app.get('/api/company')
async def get_company(user_id: str = Depends(owner), store: Store = Depends(store_dependency)):
    rows = await store.rows('companies', owner_id='eq.' + user_id, select='*', limit='1')
    return rows[0] if rows else None


@app.post('/api/company', status_code=201)
async def create_company(body: CompanyInput, request: Request, user_id: str = Depends(owner), store: Store = Depends(store_dependency)):
    await limit(store, request, 'company', 10)
    if len(body.name.strip()) < 2 or not body.bot_name.strip():
        raise HTTPException(422, 'Enter a company and bot name.')
    if await store.rows('companies', owner_id='eq.' + user_id, select='id', limit='1'):
        raise HTTPException(409, 'Your account already has a company.')
    rows = await store.insert('companies', {**body.model_dump(), 'name': body.name.strip(), 'bot_name': body.bot_name.strip(), 'owner_id': user_id})
    return rows[0]


@app.patch('/api/company')
async def update_company(body: CompanyInput, user_id: str = Depends(owner), store: Store = Depends(store_dependency)):
    c = await own_company(store, user_id)
    if len(body.name.strip()) < 2 or not body.bot_name.strip():
        raise HTTPException(422, 'Enter a company and bot name.')
    rows = await store.update('companies', body.model_dump(), id='eq.' + c['id'], owner_id='eq.' + user_id)
    return rows[0]


@app.post('/api/company/publish')
async def publish(body: PublishInput, user_id: str = Depends(owner), store: Store = Depends(store_dependency)):
    c = await own_company(store, user_id)
    if body.published:
        ready = await store.rows('documents', company_id='eq.' + c['id'], is_approved='eq.true', status='eq.ready', select='id', limit='1')
        if not ready:
            raise HTTPException(409, 'Upload and approve at least one ready document first.')
    return (await store.update('companies', {'is_published': body.published}, id='eq.' + c['id']))[0]


@app.get('/api/documents')
async def documents(user_id: str = Depends(owner), store: Store = Depends(store_dependency)):
    c = await own_company(store, user_id)
    return await store.rows('documents', company_id='eq.' + c['id'], select=DOC_FIELDS, order='created_at.desc', limit='100')


async def process_document(store, doc, data):
    claimed = await store.update('documents', {'status': 'processing', 'error_message': None, 'is_approved': False},
                                 id='eq.' + doc['id'], company_id='eq.' + doc['company_id'], status='in.(uploaded,failed)')
    if not claimed:
        raise HTTPException(409, 'This file is already processing or ready.')
    try:
        chunks = await run_in_threadpool(extract, data, doc['filename'])
        await store.rpc('ingest_chunks', {'p_document': doc['id'], 'p_company': doc['company_id'], 'p_chunks': chunks})
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'Processing failed. Check the file and retry.'
        await store.update('documents', {'status': 'failed', 'is_approved': False, 'error_message': message[:300]},
                           id='eq.' + doc['id'], company_id='eq.' + doc['company_id'])
        return {**doc, 'status': 'failed', 'is_approved': False, 'error_message': message[:300]}
    return {**doc, 'status': 'ready', 'is_approved': False, 'error_message': None}


@app.post('/api/documents', status_code=201)
async def upload_document(request: Request, file: UploadFile = File(...), user_id: str = Depends(owner), store: Store = Depends(store_dependency)):
    c = await own_company(store, user_id)
    await limit(store, request, 'upload:' + c['id'], 5)
    existing = await store.rows('documents', company_id='eq.' + c['id'], select='id', limit='100')
    if len(existing) >= 30:
        raise HTTPException(409, 'Pilot limit: 30 documents per company. Delete an old file first.')
    data = await file.read(MAX_BYTES + 1)
    filename = (file.filename or '').replace('\\', '/').split('/')[-1][:180]
    if Path(filename).suffix.lower() not in {'.pdf', '.docx', '.txt'} or not data or len(data) > MAX_BYTES:
        raise HTTPException(422, 'Upload a non-empty PDF, DOCX or TXT file up to 10 MB.')
    path = c['id'] + '/' + str(uuid4()) + Path(filename).suffix.lower()
    await store.upload(path, data)
    try:
        doc = (await store.insert('documents', {'company_id': c['id'], 'filename': filename, 'storage_path': path}))[0]
    except Exception:
        await store.remove_file(path)
        raise
    result = await process_document(store, doc, data)
    return {k: v for k, v in result.items() if k != 'storage_path'}


@app.post('/api/documents/{document_id}/retry')
async def retry_document(document_id: UUID, request: Request, user_id: str = Depends(owner), store: Store = Depends(store_dependency)):
    c, doc = await own_document(store, user_id, document_id)
    await limit(store, request, 'upload:' + c['id'], 5)
    if doc['status'] not in ('failed', 'uploaded'):
        raise HTTPException(409, 'Only failed or interrupted uploads can be retried.')
    data = await store.download(doc['storage_path'])
    result = await process_document(store, doc, data)
    return {k: v for k, v in result.items() if k != 'storage_path'}


@app.patch('/api/documents/{document_id}/approval')
async def approve_document(document_id: UUID, body: ApprovalInput, user_id: str = Depends(owner), store: Store = Depends(store_dependency)):
    c, doc = await own_document(store, user_id, document_id)
    if body.approved and doc['status'] != 'ready':
        raise HTTPException(409, 'Only a ready document can be approved.')
    result = await store.update('documents', {'is_approved': body.approved}, id='eq.' + str(document_id), company_id='eq.' + c['id'])
    return {k: v for k, v in result[0].items() if k != 'storage_path'}


@app.delete('/api/documents/{document_id}', status_code=204)
async def delete_document(document_id: UUID, user_id: str = Depends(owner), store: Store = Depends(store_dependency)):
    c, doc = await own_document(store, user_id, document_id)
    if doc['status'] == 'processing':
        raise HTTPException(409, 'Wait for processing to finish before deleting.')
    # Revoke retrieval first, then remove the private object and its database record.
    await store.update('documents', {'is_approved': False}, id='eq.' + str(document_id), company_id='eq.' + c['id'])
    await store.remove_file(doc['storage_path'])
    await store.delete('documents', id='eq.' + str(document_id), company_id='eq.' + c['id'])


@app.get('/api/bots/{slug}')
async def get_bot(slug: str, request: Request, preview: bool = False, store: Store = Depends(store_dependency)):
    c = await visible_company(store, slug, request, preview)
    return {k: c[k] for k in ('name','bot_name','welcome_message','slug')}


@app.post('/api/bots/{slug}/chat')
async def chat(slug: str, body: ChatInput, request: Request, preview: bool = False, store: Store = Depends(store_dependency)):
    c = await visible_company(store, slug, request, preview)
    await limit(store, request, 'chat:' + c['id'], 10)
    daily = max(1, min(int(os.getenv('BOT_DAILY_LIMIT', '100')), 10000))
    if not await store.rpc('consume_limit', {'p_key': 'bot-total:' + c['id'], 'p_limit': daily, 'p_seconds': 86400}):
        raise HTTPException(429, 'This bot has reached its daily pilot allowance. Please contact the company.')
    question = body.question.strip()
    if len(question) < 2:
        raise HTTPException(422, 'Enter a question.')
    passages = await store.rpc('search_knowledge', {'p_company': c['id'], 'p_question': question})
    if not passages:
        return {'answer': FALLBACK, 'sources': []}
    answer = await generate(question, passages)
    cited = sorted({int(n) for n in re.findall(r'\[(\d+)\]', answer)})
    # No untraceable answer is presented as grounded company knowledge.
    if not cited or any(i < 1 or i > len(passages) for i in cited):
        return {'answer': FALLBACK, 'sources': []}
    sources = [{'number': i, 'filename': passages[i-1]['filename'], 'page_number': passages[i-1]['page_number'],
                'excerpt': passages[i-1]['content'][:1200]} for i in cited]
    return {'answer': answer, 'sources': sources}


@app.post('/api/bots/{slug}/enquiries', status_code=201)
async def enquiry(slug: str, body: EnquiryInput, request: Request, store: Store = Depends(store_dependency)):
    c = await visible_company(store, slug, request)
    await limit(store, request, 'enquiry:' + c['id'], 3, 3600)
    if not body.consent or not body.name.strip() or not body.message.strip():
        raise HTTPException(422, 'Confirm permission to share your details with the company.')
    await store.insert('enquiries', {'company_id': c['id'], 'name': body.name.strip(), 'email': body.email, 'message': body.message.strip()})
    return {'message': 'Your enquiry is saved for the company owner to review.'}


@app.get('/api/enquiries')
async def enquiries(user_id: str = Depends(owner), store: Store = Depends(store_dependency)):
    c = await own_company(store, user_id)
    return await store.rows('enquiries', company_id='eq.' + c['id'], select='id,name,email,message,created_at', order='created_at.desc', limit='100')


@app.delete('/api/enquiries/{enquiry_id}', status_code=204)
async def delete_enquiry(enquiry_id: UUID, user_id: str = Depends(owner), store: Store = Depends(store_dependency)):
    c = await own_company(store, user_id)
    await store.delete('enquiries', id='eq.' + str(enquiry_id), company_id='eq.' + c['id'])
