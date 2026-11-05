import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { authenticate, logout, restoreSession } from '../services/auth'
import type { SessionIdentity } from '../services/auth'
import { onSessionExpired } from '../services/http'
import { AuthContext } from '../context/AuthContext'
import LandingPage from './LandingPage'
import { screenFromHash } from '../utils/publicNavigation'

export default function AuthGate({ children }: { children: ReactNode }) {
  const [screen, setScreen] = useState(() => screenFromHash(typeof window === 'undefined' ? '' : window.location.hash))
  const [identity, setIdentity] = useState<SessionIdentity | null>(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const navigate = () => setScreen(screenFromHash(window.location.hash))
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])

  useEffect(() => {
    let active = true
    async function restore() {
      try {
        const current = await restoreSession()
        if (active) setIdentity(current)
      } catch (err: unknown) {
        if (active) setError(err instanceof Error ? err.message : 'Não foi possível verificar a sessão.')
      } finally { if (active) setLoading(false) }
    }
    const unsubscribe = onSessionExpired(() => {
      setIdentity(null)
      window.location.hash = 'login'
      setError('Sua sessão expirou. Entre novamente.')
    })
    void restore()
    // Re-check when returning to the tab, including a login/logout in another tab.
    window.addEventListener('focus', restore)
    return () => { active = false; unsubscribe(); window.removeEventListener('focus', restore) }
  }, [retry])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setError(null)
    if (mode === 'register' && password !== confirmation) { setError('As senhas não conferem.'); return }
    setBusy(true)
    try {
      const current = await authenticate(mode, email, password)
      setPassword('')
      setConfirmation('')
      setIdentity(current)
      window.location.hash = 'app'
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'Não foi possível entrar.') }
    finally { setBusy(false) }
  }

  async function signOut() {
    if (busy) return
    setBusy(true)
    setError(null)
    try { await logout(); setIdentity(null); setPassword(''); setConfirmation(''); window.location.hash = 'login' }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Não foi possível sair.') }
    finally { setBusy(false) }
  }

  if (screen === 'landing') return <LandingPage authenticated={Boolean(identity)} />
  if (loading) return <main className="dashboard"><p role="status">Verificando sessão...</p></main>
  if (identity) return <AuthContext.Provider value={{ ...identity, logout: signOut, loggingOut: busy }}>
    <div key={`${identity.user.id}-${identity.workspace.id}`}>{error && <p className="error-message" role="alert">{error}</p>}{children}</div>
  </AuthContext.Provider>

  return <main className="dashboard">
    <a href="#inicio">Voltar ao início</a>
    <p className="eyebrow">Aurora / Acesso</p>
    <h1>{mode === 'login' ? 'Entrar na Aurora' : 'Criar conta'}</h1>
    <p>Os membros do seu espaço de trabalho compartilham a mesma base financeira.</p>
    {mode === 'register' && <p className="data-note">Demonstração: novas contas entram no espaço Aurora e veem os dados compartilhados. Use somente dados fictícios. Este cadastro não concede acesso a departamentos reais.</p>}
    <form className="entry-form" onSubmit={submit}>
      <fieldset disabled={busy}><div className="entry-fields">
        <label>Email<input type="email" required maxLength={254} autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label>Senha<input type="password" required minLength={8} maxLength={128} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        {mode === 'register' && <label>Repita a senha<input type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label>}
      </div>
      <p>Use uma senha de 8 a 128 caracteres. Espaços são permitidos.</p>
      <button className="primary-button" type="submit">{busy ? 'Aguarde...' : mode === 'login' ? 'Entrar' : 'Cadastrar'}</button>
      </fieldset>
    </form>
    {error && <p className="error-message" role="alert">{error}</p>}
    <div className="pagination">
      <button className="secondary-button" type="button" disabled={busy} onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setPassword(''); setConfirmation(''); setError(null) }}>{mode === 'login' ? 'Criar uma conta' : 'Já tenho uma conta'}</button>
      <button className="secondary-button" type="button" disabled={busy} onClick={() => setRetry((value) => value + 1)}>Verificar sessão novamente</button>
    </div>
  </main>
}
