import { useEffect, useRef, useState } from 'react'
import { api, errorText } from './api'

type Company = { id: string; slug: string; is_published: boolean }
type Doc = { id: string; filename: string; status: string; is_approved: boolean; error_message: string | null }
type Enquiry = { id: string; name: string; email: string; message: string; created_at: string }
export default function KnowledgeWorkspace({ company, onPublished }: { company: Company; onPublished: (published: boolean) => void }) {
  const [docs, setDocs] = useState<Doc[]>([])
  const [enquiries, setEnquiries] = useState<Enquiry[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const fileInput = useRef<HTMLInputElement>(null)
  const link = `${window.location.origin}/bot/${company.slug}`
  async function refresh() {
    const [d, e] = await Promise.all([api<Doc[]>('/documents'), api<Enquiry[]>('/enquiries')])
    setDocs(d); setEnquiries(e)
  }
  useEffect(() => {
    let active = true
    Promise.all([api<Doc[]>('/documents'), api<Enquiry[]>('/enquiries')])
      .then(([d, e]) => { if (active) { setDocs(d); setEnquiries(e) } })
      .catch(e => { if (active) { setMessage(errorText(e)); setLoadFailed(true) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [company.id, attempt])
  async function act(task: () => Promise<unknown>, success = '') {
    setBusy(true); setMessage('')
    try { await task(); await refresh(); setMessage(success) }
    catch (e) { setMessage(errorText(e)); try { await refresh() } catch { /* keep the original message */ } }
    finally { setBusy(false) }
  }
  async function upload(file?: File) {
    if (!file) return
    if (file.size > 10 * 1024 * 1024) { setMessage('Use a file no larger than 10 MB.'); return }
    const body = new FormData(); body.append('file', file)
    await act(async () => { const d = await api<Doc>('/documents', {method:'POST', body}); if (d.status === 'failed') throw new Error(d.error_message || 'Processing failed.') }, 'File processed. Review its content before approving it for answers.')
    if (fileInput.current) fileInput.current.value = ''
  }
  return <section className="knowledge-workspace" aria-label="Company knowledge workspace">
    <h2>Your knowledge workspace</h2>
    {message && <p role="status" className="knowledge-notice">{message}</p>}
    {loading ? <p>Loading documents…</p> : loadFailed ? <button type="button" onClick={() => {setLoading(true); setLoadFailed(false); setAttempt(attempt + 1)}}>Retry loading workspace</button> : <>
      <div className="knowledge-section">
        <h3>1. Add company knowledge</h3>
        <p>Upload PDF, DOCX or TXT files. Maximum 10 MB, 100 PDF pages. Scanned documents need OCR and are not supported yet.</p>
        <input ref={fileInput} type="file" aria-label="Upload document" accept=".pdf,.docx,.txt" disabled={busy} onChange={e => void upload(e.target.files?.[0])} />
        {busy && <p role="status">Working… Please wait before leaving this page.</p>}
        {docs.length === 0 && <p>No documents yet. Upload your FAQ, service guide, or company policies.</p>}
        {docs.map(d => <article className="knowledge-document" key={d.id}>
          <strong>{d.filename}</strong><small>Status: {d.status}</small>
          {d.error_message && <p role="alert">{d.error_message}</p>}
          <div className="knowledge-actions">
            <label className="knowledge-checkbox"><input type="checkbox" checked={d.is_approved} disabled={busy || d.status !== 'ready'} onChange={() => void act(() => api(`/documents/${d.id}/approval`, {method:'PATCH', body:JSON.stringify({approved:!d.is_approved})}))} />Approved for answers</label>
            {['uploaded','failed'].includes(d.status) && <button type="button" disabled={busy} onClick={() => void act(async () => {const result = await api<Doc>(`/documents/${d.id}/retry`, {method:'POST'}); if(result.status==='failed') throw new Error(result.error_message || 'Retry failed.')})}>Retry</button>}
            <button type="button" className="knowledge-delete" disabled={busy || d.status === 'processing'} onClick={() => {if (window.confirm(`Delete ${d.filename} and remove its knowledge?`)) void act(() => api(`/documents/${d.id}`, {method:'DELETE'}))}}>Delete</button>
          </div>
        </article>)}
      </div>
      <div className="knowledge-section">
        <h3>2. Preview and share your bot</h3>
        <p>Only ready, approved documents power answers. Publishing makes their extracted content accessible through the bot.</p>
        <a className="knowledge-link" href={link + '?preview=1'} target="_blank" rel="noreferrer">Preview your assistant ↗</a>
        <button type="button" disabled={busy} onClick={() => void act(async () => {const c = await api<{is_published:boolean}>('/company/publish', {method:'POST',body:JSON.stringify({published:!company.is_published})}); onPublished(c.is_published)}, company.is_published ? 'Assistant unpublished.' : 'Assistant published.')}>{company.is_published ? 'Unpublish bot' : 'Publish bot'}</button>
        <label>Your customer link<input readOnly value={link} onFocus={e => e.target.select()} /></label>
        <button type="button" disabled={!company.is_published} onClick={async () => {try {await navigator.clipboard.writeText(link);setMessage('Link copied.')} catch {setMessage('Select and copy the customer link above.')}}}>Copy customer link</button>
        {!company.is_published && <small>The customer link becomes accessible after publishing.</small>}
      </div>
      <div className="knowledge-section"><h3>Customer enquiries</h3>{enquiries.length === 0 ? <p>No enquiries yet.</p> : enquiries.map(e => <article className="knowledge-document" key={e.id}><strong>{e.name}</strong><a href={'mailto:'+e.email}>{e.email}</a><small>{new Date(e.created_at).toLocaleString()}</small><p>{e.message}</p><button type="button" className="knowledge-delete" disabled={busy} onClick={() => {if(window.confirm('Delete this enquiry and contact details?')) void act(() => api(`/enquiries/${e.id}`, {method:'DELETE'}))}}>Delete enquiry</button></article>)}</div>
    </>}
  </section>
}
