import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api, errorText } from './api'

type Source = {number: number; filename: string; page_number: number; excerpt: string}
type Reply = {answer: string; sources: Source[]}
type Bot = {name: string; bot_name: string; welcome_message: string}
export default function PublicBot({slug}: {slug: string}) {
  const preview = new URLSearchParams(window.location.search).get('preview') === '1'
  const suffix = preview ? '?preview=true' : ''
  const [bot, setBot] = useState<Bot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [loadError, setLoadError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState<{role: string; text: string; sources?: Source[]}[]>([])
  const [enquiryStatus, setEnquiryStatus] = useState('')
  const [sendingEnquiry, setSendingEnquiry] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let active = true
    api<Bot>(`/bots/${encodeURIComponent(slug)}${suffix}`).then(b => {if(active)setBot(b)}).catch(e => {if(active)setLoadError(errorText(e))}).finally(() => {if(active)setLoading(false)})
    return () => {active = false}
  }, [slug, suffix, attempt])
  useEffect(() => {end.current?.scrollIntoView({behavior:'smooth',block:'end'})}, [messages, busy])
  async function send(event: FormEvent) {
    event.preventDefault(); const q = question.trim(); if(q.length<2 || busy)return
    setQuestion(''); setBusy(true); setError(''); setMessages(m => [...m,{role:'user',text:q}])
    try {const r = await api<Reply>(`/bots/${encodeURIComponent(slug)}/chat${suffix}`,{method:'POST',body:JSON.stringify({question:q})});setMessages(m => [...m,{role:'assistant',text:r.answer,sources:r.sources}])}
    catch(e){setError(errorText(e));setQuestion(q)}finally{setBusy(false)}
  }
  async function enquiry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setSendingEnquiry(true); setEnquiryStatus('')
    try {const r = await api<{message:string}>(`/bots/${encodeURIComponent(slug)}/enquiries`,{method:'POST',body:JSON.stringify({name:data.get('name'),email:data.get('email'),message:data.get('message'),consent:data.get('consent')==='on'})});setEnquiryStatus(r.message);form.reset()}
    catch(e){setEnquiryStatus(errorText(e))}finally{setSendingEnquiry(false)}
  }
  return <main className="public-bot"><header><a href="/">Multicombot</a><span>Company knowledge assistant</span></header>
    {preview && <p className="knowledge-notice">Owner preview · Only approved documents are used. Publish your bot before sharing it.</p>}
    {loading ? <p role="status">Opening assistant…</p> : loadError ? <section><h1>Assistant unavailable</h1><p role="alert">{loadError}</p><button onClick={() => {setLoading(true); setLoadError(''); setAttempt(attempt + 1)}}>Try again</button></section> : bot && <>
      <section className="bot-intro"><p className="eyebrow">{bot.name}</p><h1>{bot.bot_name}</h1><p>{bot.welcome_message}</p></section>
      <section className="bot-messages" aria-live="polite">{messages.length === 0 && <p className="bot-hint">Ask a specific question about the company. Each question is searched independently.</p>}{messages.map((m,i) => <article key={i} className={'bot-message '+m.role}><strong>{m.role==='user'?'You':bot.bot_name}</strong><p>{m.text}</p>{m.sources?.map(s => <details key={s.number}><summary>[{s.number}] {s.filename}{s.page_number>0?` · Page ${s.page_number}`:''}</summary><p>{s.excerpt}</p></details>)}</article>)}{busy && <p role="status">Searching approved documents…</p>}<div ref={end} /></section>
      {error && <p className="knowledge-notice" role="alert">{error}</p>}
      <form onSubmit={send} className="bot-composer"><label htmlFor="bot-question">Your question</label><div><input id="bot-question" required minLength={2} maxLength={1000} placeholder="What would you like to know?" value={question} disabled={busy} onChange={e => setQuestion(e.target.value)} /><button disabled={busy || question.trim().length<2}>{busy?'Thinking…':'Send'}</button></div></form>
      <small>AI can make mistakes. Check the source excerpts. Avoid sharing sensitive personal information.</small>
      {!preview && <details className="bot-contact"><summary>Contact the company</summary><p>Your enquiry is saved for the owner to review. This does not send an email or book an appointment.</p><form onSubmit={enquiry}><label>Your name<input name="name" required minLength={2} maxLength={100} /></label><label>Email<input name="email" type="email" required maxLength={254} /></label><label>Your enquiry<textarea name="message" required minLength={5} maxLength={2000} /></label><label className="knowledge-checkbox"><input name="consent" type="checkbox" required />I agree to share these details with this company so they can respond.</label><button disabled={sendingEnquiry}>{sendingEnquiry?'Sending…':'Submit enquiry'}</button></form>{enquiryStatus && <p role="status">{enquiryStatus}</p>}</details>}
    </>}
  </main>
}
