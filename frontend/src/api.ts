import { supabase } from './supabase'
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const { data } = await supabase.auth.getSession()
  const headers = new Headers(options.headers)
  if (data.session) headers.set('Authorization', `Bearer ${data.session.access_token}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch((import.meta.env.VITE_API_URL || '') + '/api' + path, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}). Check the API and form fields.`)
  }
  return response.status === 204 ? undefined as T : response.json()
}
export function errorText(e: unknown) { return e instanceof Error ? e.message : 'Something went wrong. Please retry.' }
