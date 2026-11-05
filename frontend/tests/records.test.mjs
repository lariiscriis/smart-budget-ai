import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import { fileURLToPath } from 'node:url'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let vite, campaigns, incomes, entries, categories, validation, components, Attribution
before(async () => {
  vite = await createServer({
    root: fileURLToPath(new URL('../', import.meta.url)), configFile: false, envDir: false,
    define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://api.test/') },
    server: { middlewareMode: true, watch: null, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true, include: [] },
  })
  campaigns = await vite.ssrLoadModule('/src/services/campaigns.ts')
  incomes = await vite.ssrLoadModule('/src/services/incomes.ts')
  entries = await vite.ssrLoadModule('/src/services/entries.ts')
  categories = await vite.ssrLoadModule('/src/services/categories.ts')
  validation = await vite.ssrLoadModule('/src/utils/entryForm.ts')
  components = await Promise.all(['FinancialEntryPanel', 'CampaignSelect', 'CampaignsPanel', 'IncomeListPanel'].map(async (name) => {
    return (await vite.ssrLoadModule(`/src/components/${name}.tsx`)).default
  }))
  Attribution = (await vite.ssrLoadModule('/src/components/RecordAttribution.tsx')).default
})
after(async () => { await vite?.close() })

const response = (data, status = 200) => new Response(JSON.stringify(data), { status })
const sampleIncome = (extra = {}) => ({ id: 3, category_id: 2, description: 'Venda', income_date: '2026-11-05', amount: '12.34', campaign_id: null, ...extra })

test('money validation preserves cents, accepts Brazilian input and keeps zero budgets', () => {
  assert.equal(validation.normalizeAmount(' 1500,5 ', true), '1500.50')
  assert.equal(validation.normalizeAmount('999999999999.99', true), '999999999999.99')
  assert.equal(validation.normalizeAmount('0', false), '0.00')
  for (const value of ['0', '0.00', '000,00', '-1', '1.001', '1.000,50', 'NaN', 'Infinity', '1e3', '1000000000000', '']) {
    assert.throws(() => validation.normalizeAmount(value, true))
  }
})

test('dates and periods reject invalid calendar dates and unsupported years', () => {
  assert.deepEqual(validation.parsePeriod('2026-11'), { year: 2026, month: 11 })
  validation.validateDate('2024-02-29')
  validation.validateDate('2100-12-31')
  for (const value of ['', '2026-13', '1999-01', '2101-01']) assert.throws(() => validation.parsePeriod(value))
  for (const value of ['', '2026-02-30', '2026-02-29', '2026-04-31', '2026-1-01']) assert.throws(() => validation.validateDate(value))
})

test('campaign creation and pagination use existing endpoints', async (t) => {
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push([url, options])
    return response(options?.method === 'POST' ? { id: 7, name: 'Natal' } : [{ id: 7, name: 'Natal' }], options?.method === 'POST' ? 201 : 200)
  })
  assert.equal((await campaigns.createCampaign('Natal')).id, 7)
  assert.equal(calls[0][0], 'http://api.test/campaigns')
  assert.deepEqual(JSON.parse(calls[0][1].body), { name: 'Natal' })
  assert.equal((await campaigns.listCampaigns(20, 20)).length, 1)
  assert.equal(calls[1][0], 'http://api.test/campaigns?offset=20&limit=20')
})

test('campaign selector loads every page, including options after the first hundred', async (t) => {
  const offsets = []
  t.mock.method(globalThis, 'fetch', async (url) => {
    const offset = Number(new URL(url).searchParams.get('offset'))
    offsets.push(offset)
    return response(Array.from({ length: offset === 0 ? 100 : 2 }, (_, index) => ({ id: offset + index + 1, name: `Campanha ${offset + index + 1}` })))
  })
  const rows = await campaigns.listAllCampaigns()
  assert.equal(rows.length, 102)
  assert.equal(rows[101].id, 102)
  assert.deepEqual(offsets, [0, 100])
})

test('income categories request income on every page and exclude incompatible types', async (t) => {
  const offsets = []
  t.mock.method(globalThis, 'fetch', async (url) => {
    const query = new URL(url).searchParams
    assert.equal(query.get('type'), 'income')
    const offset = Number(query.get('offset'))
    offsets.push(offset)
    return response(offset === 0 ? Array.from({ length: 100 }, (_, index) => ({ id: index + 1, name: 'Receita', type: 'income' })) : [{ id: 101, name: 'Despesa', type: 'expense' }])
  })
  assert.equal((await categories.listAllCategories('income')).length, 100)
  assert.deepEqual(offsets, [0, 100])
})

test('income submission keeps decimal strings and supports omitted, null and selected campaign', async (t) => {
  const base = { category_id: 2, description: 'Venda', income_date: '2026-11-05', amount: '12.34' }
  for (const campaign of [{}, { campaign_id: null }, { campaign_id: 7 }]) {
    const payload = { ...base, ...campaign }
    const mock = t.mock.method(globalThis, 'fetch', async (url, options) => {
      assert.equal(url, 'http://api.test/incomes')
      assert.equal(options.method, 'POST')
      assert.deepEqual(JSON.parse(options.body), payload)
      return response(sampleIncome({ campaign_id: campaign.campaign_id ?? null }), 201)
    })
    assert.equal((await incomes.createIncome(payload)).amount, '12.34')
    mock.mock.restore()
  }
})

test('income listing sends selected period and pagination and handles empty results', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url) => {
    assert.equal(url, 'http://api.test/incomes?year=2026&month=11&offset=20&limit=20')
    return response([])
  })
  assert.deepEqual(await incomes.listIncomes(2026, 11, 20, 20), [])
})

test('expense and budget payloads preserve existing contracts', async (t) => {
  const expense = { category_id: 1, description: 'Entrega', expense_date: '2026-11-05', amount: '5.00', campaign_id: 7 }
  const budget = { category_id: 1, year: 2026, month: 11, amount: '0.00' }
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    const payload = JSON.parse(options.body)
    if (url.endsWith('/expenses')) assert.deepEqual(payload, expense)
    else {
      assert.equal(url, 'http://api.test/budgets')
      assert.deepEqual(payload, budget)
      assert.equal('campaign_id' in payload, false)
    }
    return response({ id: 1, ...payload }, 201)
  })
  await entries.createExpense(expense)
  await entries.createBudget(budget)
})

test('duplicate campaign, missing references and category type errors have useful messages', async (t) => {
  for (const [status, body, action, expected] of [
    [409, {}, () => campaigns.createCampaign('Natal'), /Já existe uma campanha/],
    [404, { detail: 'Campanha não encontrada.' }, () => incomes.createIncome({}), /Campanha não encontrada/],
    [422, { detail: "Esta operação exige uma categoria do tipo 'income'." }, () => incomes.createIncome({}), /tipo 'income'/],
    [422, { detail: [] }, () => campaigns.createCampaign(''), /nome válido/],
    [503, {}, () => incomes.listIncomes(2026, 11), /HTTP 503/],
  ]) {
    const mock = t.mock.method(globalThis, 'fetch', async () => response(body, status))
    await assert.rejects(action(), expected)
    mock.mock.restore()
  }
})

test('malformed responses are rejected and failed mutations are never retried automatically', async (t) => {
  for (const [body, action] of [
    [[{ id: -1, name: 'Inválida' }], () => campaigns.listCampaigns()],
    [[sampleIncome({ amount: 12.34 })], () => incomes.listIncomes(2026, 11)],
    [[sampleIncome({ campaign_id: -1 })], () => incomes.listIncomes(2026, 11)],
    [[sampleIncome({ income_date: '2026-02-30' })], () => incomes.listIncomes(2026, 11)],
  ]) {
    const mock = t.mock.method(globalThis, 'fetch', async () => response(body))
    await assert.rejects(action(), /inesperado/)
    mock.mock.restore()
  }
  let attempts = 0
  t.mock.method(globalThis, 'fetch', async () => { attempts++; throw new TypeError('Falha de conexão') })
  await assert.rejects(campaigns.createCampaign('Natal'), /Falha de conexão/)
  assert.equal(attempts, 1)
})

test('new forms use existing styles, offer income and keep campaign optional', () => {
  const [EntryPanel, CampaignSelect, CampaignsPanel, IncomeListPanel] = components
  const entryHtml = renderToStaticMarkup(React.createElement(EntryPanel))
  assert.match(entryHtml, /value="income"/)
  assert.match(entryHtml, /value="budget"/)
  assert.match(entryHtml, /value="expense"/)
  const selectHtml = renderToStaticMarkup(React.createElement(CampaignSelect, { value: '', onChange() {}, disabled: false }))
  assert.match(selectHtml, /Campanha \(opcional\)/)
  assert.match(selectHtml, /Sem campanha/)
  assert.doesNotMatch(selectHtml, /required/)
  const campaignsHtml = renderToStaticMarkup(React.createElement(CampaignsPanel))
  assert.match(campaignsHtml, /Cadastrar campanha/)
  const listHtml = renderToStaticMarkup(React.createElement(IncomeListPanel, { period: '2026-11', onPeriodChange() {}, refresh: 0 }))
  assert.match(listHtml, /Receitas cadastradas/)
  assert.match(listHtml, /Próxima/)
})

test('record attribution distinguishes creator, latest editor and legacy responsibility', () => {
  const record = { created_by_user: { id: 1, email: 'first@example.com' }, updated_by_user: { id: 2, email: 'second@example.com' },
    created_at: '2026-11-05T12:00:00Z', updated_at: '2026-11-05T13:00:00Z', attribution_source: 'recorded' }
  const html = renderToStaticMarkup(React.createElement(Attribution, { record }))
  assert.match(html, /Criado por first@example.com/)
  assert.match(html, /Última alteração: second@example.com/)
  const legacy = renderToStaticMarkup(React.createElement(Attribution, { record: { ...record, attribution_source: 'legacy_owner' } }))
  assert.match(legacy, /Responsável legado/)
  assert.doesNotMatch(legacy, /Criado por/)
})
