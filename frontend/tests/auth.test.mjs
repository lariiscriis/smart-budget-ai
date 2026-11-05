import assert from 'node:assert/strict'
import { after, afterEach, before, test } from 'node:test'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let vite, auth, http, AuthGate, LandingPage
const csrf = 'a'.repeat(64)
const user = { id: 42, email: 'person@example.com' }
const workspace = { id: 1, name: 'Aurora', is_demo: true }
before(async () => {
  vite = await createServer({
    root: fileURLToPath(new URL('../', import.meta.url)), configFile: false, envDir: false,
    define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://api.test') },
    server: { middlewareMode: true, watch: null, ws: false, hmr: false },
    optimizeDeps: { noDiscovery: true, include: [] },
  })
  http = await vite.ssrLoadModule('/src/services/http.ts')
  auth = await vite.ssrLoadModule('/src/services/auth.ts')
  AuthGate = (await vite.ssrLoadModule('/src/components/AuthGate.tsx')).default
  LandingPage = (await vite.ssrLoadModule('/src/components/LandingPage.tsx')).default
})
afterEach(() => http.setCsrfToken(null))
after(async () => { await vite?.close() })

test('login sends credentials to backend and exposes only user plus in-memory CSRF', async (t) => {
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push([url, options])
    return new Response(JSON.stringify({ user, workspace, csrf_token: csrf }))
  })
  assert.deepEqual(await auth.authenticate('login', ' person@example.com ', 'Abc123!?'), { user, workspace })
  assert.equal(calls[0][0], 'http://api.test/auth/login')
  assert.equal(calls[0][1].credentials, 'include')
  assert.equal(calls[0][1].headers.get('X-Aurora-Request'), '1')
  assert.equal(JSON.parse(calls[0][1].body).email, user.email)
  assert.equal(JSON.parse(calls[0][1].body).password, 'Abc123!?')
  await http.authFetch('http://api.test/expenses', { method: 'POST' })
  assert.equal(calls[1][1].headers.get('X-CSRF-Token'), csrf)
  assert.equal(calls[1][1].cache, 'no-store')
})

test('reload restores the session from HttpOnly cookie through me', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'http://api.test/auth/me')
    assert.equal(options.credentials, 'include')
    return new Response(JSON.stringify({ user, workspace, csrf_token: csrf }))
  })
  assert.deepEqual(await auth.restoreSession(), { user, workspace })
})

test('logout clears CSRF and expired financial requests notify the gate', async (t) => {
  let expired = 0
  const unsubscribe = http.onSessionExpired(() => expired++)
  http.setCsrfToken(csrf)
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (url.endsWith('/auth/logout')) {
      assert.equal(options.headers.get('X-CSRF-Token'), csrf)
      return new Response(null, { status: 204 })
    }
    assert.equal(options.headers.has('X-CSRF-Token'), false)
    return new Response(null, { status: 401 })
  })
  await auth.logout()
  await http.authFetch('http://api.test/expenses', { method: 'POST' })
  assert.equal(expired, 1)
  unsubscribe()
})

test('missing, invalid and failed sessions do not create an authenticated user', async (t) => {
  for (const [status, data, expected] of [[401, {}, null], [200, { user, workspace, csrf_token: 'bad' }, 'reject'], [200, { user, csrf_token: csrf }, 'reject'], [503, {}, 'reject']]) {
    const mocked = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(data), { status }))
    if (expected === null) assert.equal(await auth.restoreSession(), null)
    else await assert.rejects(auth.restoreSession())
    mocked.mock.restore()
  }
})

test('direct login and application links keep financial UI behind session verification', () => {
  const previous = globalThis.window
  try {
    for (const hash of ['#login', '#app', '#dashboard']) {
      globalThis.window = { location: { hash } }
      const html = renderToStaticMarkup(React.createElement(AuthGate, null, React.createElement('section', null, 'PRIVATE-FINANCES')))
      assert.match(html, /Verificando sessão/)
      assert.doesNotMatch(html, /PRIVATE-FINANCES/)
    }
  } finally {
    if (previous === undefined) delete globalThis.window
    else globalThis.window = previous
  }
})

test('public entry renders the landing without financial data', () => {
  const html = renderToStaticMarkup(React.createElement(AuthGate, null, React.createElement('section', null, 'PRIVATE-FINANCES')))
  assert.match(html, /Cuidado natural/)
  assert.match(html, /href="#login"/)
  assert.doesNotMatch(html, /PRIVATE-FINANCES/)
})

test('landing offers login to visitors and direct application access to authenticated members', () => {
  const visitor = renderToStaticMarkup(React.createElement(LandingPage))
  assert.match(visitor, /Entrar no sistema/)
  assert.match(visitor, /href="#login"/)
  assert.match(visitor, /Marca fictícia · Projeto de demonstração/)
  const member = renderToStaticMarkup(React.createElement(LandingPage, { authenticated: true }))
  assert.match(member, /Ir para a aplicação/)
  assert.match(member, /href="#app"/)
  assert.doesNotMatch(member, /href="#login"/)
})
