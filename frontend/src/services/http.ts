let csrfToken: string | null = null
const listeners = new Set<() => void>()

export function getApiBaseUrl(): string {
  // The development proxy keeps cookies on one host even if local .env uses 127.0.0.1.
  if (import.meta.env.DEV && typeof window !== 'undefined') return '/api'
  return (import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? '/api').replace(/\/$/, '')
}

export function setCsrfToken(value: string | null) { csrfToken = value }
export function onSessionExpired(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers)
  const method = (options.method ?? 'GET').toUpperCase()
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    headers.set('X-Aurora-Request', '1')
    if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  }
  const response = await fetch(url, { ...options, headers, credentials: 'include', cache: 'no-store' })
  if (response.status === 401 && !url.includes('/auth/')) {
    csrfToken = null
    listeners.forEach((listener) => listener())
  }
  return response
}
