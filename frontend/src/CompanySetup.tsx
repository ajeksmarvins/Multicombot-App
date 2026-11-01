import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { supabase } from './supabase'

type Company = {
  id: string
  name: string
  bot_name: string
  is_published: boolean
}

export default function CompanySetup({ ownerId }: { ownerId: string }) {
  const [company, setCompany] = useState<Company | null>(null)
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [botName, setBotName] = useState('Company Assistant')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [loadFailed, setLoadFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true

    async function loadCompany() {
      setLoading(true)
      setLoadFailed(false)
      setMessage('')

      try {
        const { data, error } = await supabase
          .from('companies')
          .select('id, name, bot_name, is_published')
          .eq('owner_id', ownerId)
          .maybeSingle()

        if (error) throw error
        if (active) setCompany(data)
      } catch (error) {
        if (active) {
          setLoadFailed(true)
          setMessage(
            error instanceof Error
              ? error.message
              : 'Could not load your company. Please retry.',
          )
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    void loadCompany()

    return () => {
      active = false
    }
  }, [ownerId, attempt])

  async function createCompany(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (name.trim().length < 2 || !botName.trim()) {
      setMessage('Enter a company name and bot name.')
      return
    }

    setBusy(true)
    setMessage('')

    try {
      const { data, error } = await supabase
        .from('companies')
        .insert({
          owner_id: ownerId,
          name: name.trim(),
          bot_name: botName.trim(),
        })
        .select('id, name, bot_name, is_published')
        .single()

      if (error) {
        setMessage(error.message)
        return
      }

      setCompany(data)
    } catch {
      setMessage('Could not reach the server. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return <p role="status">Loading your company…</p>
  }

  if (loadFailed) {
    return (
      <div>
        <p role="alert">{message}</p>
        <button onClick={() => setAttempt(attempt + 1)}>
          Retry
        </button>
      </div>
    )
  }

  if (company) {
    return (
      <div>
        <h1>{company.name}</h1>
        <p className="subtitle">Your company workspace is ready.</p>
        <p><strong>Bot:</strong> {company.bot_name}</p>
        <p>
          <strong>Status:</strong>{' '}
          {company.is_published ? 'Published' : 'Draft'}
        </p>
        <p>
          Next, we’ll add document uploads and approval before
          making your bot available to customers.
        </p>
      </div>
    )
  }

  return (
    <div>
      <h1>Set up your company.</h1>
      <p className="subtitle">
        Give your workspace and knowledge bot a name.
      </p>

      <form onSubmit={createCompany}>
        <label htmlFor="company-name">Company name</label>
        <input
          id="company-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          minLength={2}
          maxLength={100}
          required
          disabled={busy}
        />

        <label htmlFor="bot-name">Bot name</label>
        <input
          id="bot-name"
          value={botName}
          onChange={(event) => setBotName(event.target.value)}
          maxLength={100}
          required
          disabled={busy}
        />

        <button type="submit" disabled={busy}>
          {busy ? 'Creating…' : 'Create company'}
        </button>
      </form>

      {message && <p role="alert">{message}</p>}
    </div>
  )
}