import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let vite, charts, api, format
before(async () => {
  vite = await createServer({
    root: fileURLToPath(new URL('../', import.meta.url)),
    configFile: false,
    envDir: false,
    define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://api.test') },
    server: { middlewareMode: true, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] },
  })
  charts = await vite.ssrLoadModule('/src/components/FinancialCharts.tsx')
  api = await vite.ssrLoadModule('/src/services/dashboard.ts')
  format = await vite.ssrLoadModule('/src/utils/format.ts')
})
after(async () => { await vite?.close() })

test('money formatting keeps exact cents and large decimal strings', () => {
  assert.equal(format.formatMoney('1234567890123.45'), 'R$ 1.234.567.890.123,45')
  assert.equal(format.formatMoney('-0.01'), '−R$ 0,01')
  assert.equal(format.formatMoney('0.00'), 'R$ 0,00')
})

test('monthly chart renders zero values without invalid coordinates and includes accessible exact values', () => {
  const html = renderToStaticMarkup(React.createElement(charts.MonthlyChart, {
    data: [{ year: 2026, month: 11, income: '0.00', expenses: '0.00', balance: '0.00', income_count: 0, expense_count: 0 }],
  }))
  assert.match(html, /role="img"/)
  assert.match(html, /nov\/26/)
  assert.match(html, /despesas R\$ 0,00/)
  assert.doesNotMatch(html, /NaN|Infinity/)
})

test('grouped bars show both exact values, escape category names and handle zero', () => {
  const html = renderToStaticMarkup(React.createElement(charts.HorizontalBars, {
    rows: [{ id: '1', label: '<script>categoria</script>', first: '0.00', second: '12.34' }],
    firstLabel: 'Previsto', secondLabel: 'Realizado',
  }))
  assert.match(html, /R\$ 12,34/)
  assert.match(html, /width:0%/)
  assert.match(html, /width:100%/)
  assert.match(html, /&lt;script&gt;/)
  assert.doesNotMatch(html, /<script>|NaN|Infinity/)
})

function responseData() {
  return {
    year: 2026, month: 11, currency: 'BRL', income_total: '0.00', expense_total: '0.00', cash_balance: '0.00',
    budget_summary: { year: 2026, month: 11, currency: 'BRL', planned: '0.00', actual: '0.00', balance: '0.00', utilization_percentage: null },
    monthly: [{ year: 2026, month: 11, income: '0.00', expenses: '0.00', balance: '0.00', income_count: 0, expense_count: 0 }],
    categories: [], campaigns: [],
  }
}

test('dashboard requests its real API contract with the selected period and abort signal', async (t) => {
  const signal = new AbortController().signal
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'http://api.test/dashboard/analytics?year=2026&month=11&months=12')
    assert.equal(options.signal, signal)
    return new Response(JSON.stringify(responseData()), { status: 200 })
  })
  assert.equal((await api.getDashboardAnalytics(2026, 11, 12, signal)).currency, 'BRL')
})

test('dashboard rejects malformed responses and mismatched periods', async (t) => {
  for (const mutate of [
    (data) => { data.income_total = 12 },
    (data) => { data.month = 10; data.budget_summary.month = 10 },
    (data) => { data.monthly = [] },
    (data) => { data.monthly[0].month = 10 },
    (data) => { data.campaigns = [{ campaign_id: -1 }] },
  ]) {
    const data = responseData()
    mutate(data)
    const mock = t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify(data)))
    await assert.rejects(api.getDashboardAnalytics(2026, 11, 12, new AbortController().signal), /inesperado/)
    mock.mock.restore()
  }
})

test('dashboard reports unavailable API instead of generating fallback values', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response('', { status: 503 }))
  await assert.rejects(api.getDashboardAnalytics(2026, 11, 12, new AbortController().signal), /HTTP 503/)
})
