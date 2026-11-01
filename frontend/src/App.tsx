import CompanySetup from './CompanySetup'
import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './supabase'
import './App.css'

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [signup, setSignup] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        setSession(nextSession)
        setLoading(false)
      },
    )

    return () => data.subscription.unsubscribe()
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setMessage('')

    try {
      if (signup) {
        const { data, error } = await supabase.auth.signUp({
          email: email.trim(),
          password,
          options: {
            emailRedirectTo: window.location.origin,
          },
        })

        if (error) throw error

        setMessage(
          data.session
            ? 'Account created.'
            : 'Check your email for a confirmation link, then sign in.',
        )
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        })

        if (error) throw error
      }

      setPassword('')
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : 'Something went wrong.',
      )
    } finally {
      setBusy(false)
    }
  }

  async function signOut() {
    setBusy(true)
    setMessage('')

    try {
      const { error } = await supabase.auth.signOut()
      if (error) throw error
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : 'Could not sign out.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="brand-mark">M</div>
        <p className="eyebrow">MULTICOMBOT</p>

        {loading ? (
          <p role="status">Loading your account…</p>
        ) : session ? (
          <>
            <CompanySetup
  key={session.user.id}
  ownerId={session.user.id}
/>
            <button disabled={busy} onClick={signOut}>
              {busy ? 'Please wait…' : 'Sign out'}
            </button>
          </>
        ) : (
          <>
            <h1>{signup ? 'Create your account.' : 'Welcome back.'}</h1>
            <p className="subtitle">
              Your company’s knowledge. Your audience’s answers.
            </p>

            <form onSubmit={handleSubmit}>
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                disabled={busy}
              />

              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                autoComplete={signup ? 'new-password' : 'current-password'}
                minLength={signup ? 8 : undefined}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                disabled={busy}
              />

              {signup && (
                <small>Use at least 8 characters.</small>
              )}

              <button type="submit" disabled={busy}>
                {busy
                  ? 'Please wait…'
                  : signup
                    ? 'Create account'
                    : 'Sign in'}
              </button>
            </form>

            <button
              className="text-button"
              disabled={busy}
              onClick={() => {
                setSignup(!signup)
                setMessage('')
                setPassword('')
              }}
            >
              {signup
                ? 'Already have an account? Sign in'
                : 'New to Multicombot? Create an account'}
            </button>
          </>
        )}

        {message && <p role="status">{message}</p>}
      </section>
    </main>
  )
}