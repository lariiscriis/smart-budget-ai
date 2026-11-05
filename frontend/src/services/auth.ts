import { authFetch, getApiBaseUrl, setCsrfToken } from './http'

export type User = { id: number; email: string }
export type Workspace = { id: number; name: string; is_demo: boolean }
export type SessionIdentity = { user: User; workspace: Workspace }
type Session = SessionIdentity & { csrf_token: string }

function validSession(data: unknown): data is Session {
  if (typeof data !== 'object' || data === null) return false
  const record = data as Record<string, unknown>
  if (typeof record.user !== 'object' || record.user === null) return false
  const user = record.user as Record<string, unknown>
  if (typeof record.workspace !== 'object' || record.workspace === null) return false
  const workspace = record.workspace as Record<string, unknown>
  return typeof user.id === 'number' && Number.isSafeInteger(user.id) && user.id > 0 &&
    typeof workspace.id === 'number' && Number.isSafeInteger(workspace.id) && workspace.id > 0 &&
    typeof workspace.name === 'string' && typeof workspace.is_demo === 'boolean' &&
    typeof user.email === 'string' && typeof record.csrf_token === 'string' && /^[a-f0-9]{64}$/.test(record.csrf_token)
}

export async function restoreSession(): Promise<SessionIdentity | null> {
  const response = await authFetch(`${getApiBaseUrl()}/auth/me`)
  if (response.status === 401) { setCsrfToken(null); return null }
  if (!response.ok) throw new Error('Não foi possível verificar sua sessão. Tente novamente.')
  const data: unknown = await response.json()
  if (!validSession(data)) throw new Error('A API retornou uma sessão em formato inesperado.')
  setCsrfToken(data.csrf_token)
  return { user: data.user, workspace: data.workspace }
}

export async function authenticate(mode: 'login' | 'register', email: string, password: string): Promise<SessionIdentity> {
  const response = await authFetch(`${getApiBaseUrl()}/auth/${mode}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: email.trim(), password }),
  })
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: 'Email ou senha inválidos.', 409: 'Não foi possível cadastrar com este email. Tente entrar.',
      422: 'Informe um email válido e uma senha de 8 a 128 caracteres.',
      429: 'Muitas tentativas. Aguarde 15 minutos antes de tentar novamente.',
      403: 'Cadastro indisponível ou acesso ao espaço não autorizado. Confira o endereço e solicite acesso ao responsável.',
    }
    throw new Error(messages[response.status] ?? 'Não foi possível autenticar. Tente novamente.')
  }
  const data: unknown = await response.json()
  if (!validSession(data)) throw new Error('A API retornou uma sessão em formato inesperado.')
  setCsrfToken(data.csrf_token)
  return { user: data.user, workspace: data.workspace }
}

export async function logout(): Promise<void> {
  const response = await authFetch(`${getApiBaseUrl()}/auth/logout`, { method: 'POST' })
  if (!response.ok && response.status !== 401) throw new Error('Não foi possível encerrar a sessão. Tente novamente.')
  setCsrfToken(null)
}
