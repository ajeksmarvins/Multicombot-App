import asyncio
from io import BytesIO
import pytest
from docx import Document
from fastapi.testclient import TestClient
import knowledge as main
from main import app as application
from extraction import extract, MAX_BYTES
C1='11111111-1111-4111-8111-111111111111'
C2='22222222-2222-4222-8222-222222222222'
D1='33333333-3333-4333-8333-333333333333'
U1='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
U2='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
class FakeStore:
    def __init__(self):
        self.company={'id':C1,'owner_id':U1,'name':'Alpha','slug':C1,'bot_name':'Alpha Bot','welcome_message':'Hello','is_published':False}
        self.docs=[{'id':D1,'company_id':C2,'status':'ready','is_approved':True}]
        self.passages=[]; self.calls=[]; self.allowed=True; self.writes=[]
    async def user(self,token):
        if token=='owner': return U1
        if token=='other': return U2
        raise main.HTTPException(401,'Invalid token')
    async def rows(self,table,**filters):
        self.calls.append((table,filters))
        data=[self.company] if table=='companies' else self.docs if table=='documents' else []
        return [r.copy() for r in data if all(not v.startswith('eq.') or str(r.get(k)).lower()==v[3:].lower() for k,v in filters.items() if k not in ('select','limit','order'))]
    async def rpc(self,name,args):
        self.calls.append((name,args))
        if name=='consume_limit': return self.allowed
        if name=='search_knowledge': return self.passages
    async def update(self,table,body,**filters):
        self.writes.append((table,body,filters))
        return [{**(self.company if table=='companies' else self.docs[0]),**body}]
    async def delete(self,table,**filters): self.writes.append((table,'delete',filters))
@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_SECRET','test-secret-'*4)
    store=FakeStore(); application.dependency_overrides[main.store_dependency]=lambda:store
    with TestClient(application) as client: yield client,store
    application.dependency_overrides.clear()
def test_health(): assert TestClient(application).get('/health').json()['status']=='ok'
def test_owner_endpoints_require_auth(env):
    client,store=env
    assert client.get('/api/company').status_code==401
    assert client.get('/api/documents',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert not store.writes
def test_foreign_document_access_blocked(env):
    client,store=env
    for method,path,args in [('patch',f'/api/documents/{D1}/approval',{'json':{'approved':True}}),('delete',f'/api/documents/{D1}',{}),('post',f'/api/documents/{D1}/retry',{})]:
        assert getattr(client,method)(path,headers={'Authorization':'Bearer owner'},**args).status_code==404
    assert not store.writes
    assert all(f.get('company_id')=='eq.'+C1 for n,f in store.calls if n=='documents')
def test_draft_hidden(env):
    client,_=env
    assert client.get('/api/bots/'+C1).status_code==404
    assert client.post('/api/bots/'+C1+'/chat',json={'question':'hours?'}).status_code==404
def test_preview_owner_only(env):
    client,_=env; path='/api/bots/'+C1+'?preview=true'
    assert client.get(path).status_code==401
    assert client.get(path,headers={'Authorization':'Bearer other'}).status_code==404
    r=client.get(path,headers={'Authorization':'Bearer owner'})
    assert r.status_code==200 and 'owner_id' not in r.json()
def test_missing_knowledge_skips_llm(env,monkeypatch):
    client,store=env; store.company['is_published']=True
    async def fail(*args): raise AssertionError('LLM called without sources')
    monkeypatch.setattr(main,'generate',fail)
    assert client.post('/api/bots/'+C1+'/chat',json={'question':'hours?'}).json()=={'answer':main.FALLBACK,'sources':[]}
    assert ('search_knowledge',{'p_company':C1,'p_question':'hours?'}) in store.calls
@pytest.mark.parametrize('answer',['Open Sunday.','Open Sunday [99].'])
def test_invalid_citations_fail_closed(env,monkeypatch,answer):
    client,store=env; store.company['is_published']=True
    store.passages=[{'filename':'guide.txt','page_number':0,'content':'Open Monday.'}]
    async def generate(*args): return answer
    monkeypatch.setattr(main,'generate',generate)
    assert client.post('/api/bots/'+C1+'/chat',json={'question':'hours?'}).json()['answer']==main.FALLBACK
def test_valid_citation_mapping(env,monkeypatch):
    client,store=env; store.company['is_published']=True
    store.passages=[{'filename':'guide.txt','page_number':4,'content':'Open Monday.'}]
    async def generate(*args): return 'Open Monday [1].'
    monkeypatch.setattr(main,'generate',generate)
    r=client.post('/api/bots/'+C1+'/chat',json={'question':'hours?'}).json()
    assert r['sources']==[{'number':1,'filename':'guide.txt','page_number':4,'excerpt':'Open Monday.'}]
def test_rate_limit_before_retrieval(env):
    client,store=env; store.company['is_published']=True; store.allowed=False
    assert client.post('/api/bots/'+C1+'/chat',json={'question':'hours?'}).status_code==429
    assert not any(n=='search_knowledge' for n,_ in store.calls)
def test_publish_needs_ready_approved_document(env):
    client,_=env
    assert client.post('/api/company/publish',headers={'Authorization':'Bearer owner'},json={'published':True}).status_code==409
def test_failed_document_not_approvable(env):
    client,store=env; store.docs=[{'id':D1,'company_id':C1,'status':'failed','is_approved':False}]
    assert client.patch(f'/api/documents/{D1}/approval',headers={'Authorization':'Bearer owner'},json={'approved':True}).status_code==409
    assert not store.writes
def test_long_question_rejected(env):
    assert env[0].post('/api/bots/'+C1+'/chat',json={'question':'x'*1001}).status_code==422
def test_chunking_preserves_tail_and_overlap():
    r=extract(('a'*3000+'THE END').encode(),'notes.txt')
    assert len(r)==3 and r[-1]['content'].endswith('THE END')
    assert r[0]['content'][-150:]==r[1]['content'][:150]
@pytest.mark.parametrize('data,name',[(b'','a.txt'),(b'x','a.exe'),(b'x'*(MAX_BYTES+1),'a.txt')])
def test_invalid_uploads(data,name):
    with pytest.raises(ValueError): extract(data,name)
def test_docx_paragraphs_and_tables():
    doc=Document(); doc.add_paragraph('Company policy'); doc.add_table(rows=1,cols=2).cell(0,0).text='Delivery: two days'
    buf=BytesIO(); doc.save(buf)
    text=extract(buf.getvalue(),'guide.docx')[0]['content']
    assert 'Company policy' in text and 'Delivery: two days' in text
def test_failed_ingestion_remains_unapproved(env):
    _,store=env
    r=asyncio.run(main.process_document(store,{'id':D1,'company_id':C1,'filename':'bad.txt'},b''))
    assert r['status']=='failed' and r['is_approved'] is False
    assert not any(n=='ingest_chunks' for n,_ in store.calls)
