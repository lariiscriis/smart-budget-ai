import type { FinancialSummary } from './api'
import { authFetch, getApiBaseUrl } from './http'

export type MonthlyFlow = {
  year: number; month: number; income: string; expenses: string; balance: string
  income_count: number; expense_count: number
}
export type CategoryAnalytics = {
  category_id: number; category_name: string; planned: string; actual: string
  balance: string; expense_share_percentage: string
}
export type CampaignAnalytics = {
  campaign_id: number | null; campaign_name: string
  income: string; expenses: string; balance: string
  income_count: number; expense_count: number
}
export type DashboardAnalytics = {
  year: number; month: number; currency: 'BRL'
  income_total: string; expense_total: string; cash_balance: string
  budget_summary: FinancialSummary
  monthly: MonthlyFlow[]; categories: CategoryAnalytics[]; campaigns: CampaignAnalytics[]
}

type RecordValue = Record<string, unknown>
const record = (v: unknown): v is RecordValue => typeof v === 'object' && v !== null
const money = (v: unknown): v is string => typeof v === 'string' && /^-?\d+(\.\d{1,2})?$/.test(v) && Number.isFinite(Number(v))
const integer = (v: unknown): v is number => typeof v === 'number' && Number.isInteger(v) && v >= 0
const period = (v: RecordValue) => integer(v.year) && v.year >= 2000 && v.year <= 2100 && integer(v.month) && v.month >= 1 && v.month <= 12
const values = (v: RecordValue, keys: string[]) => keys.every((key) => money(v[key]))
const counts = (v: RecordValue) => integer(v.income_count) && integer(v.expense_count)

function isAnalytics(v: unknown): v is DashboardAnalytics {
  if (!record(v) || !period(v) || v.currency !== 'BRL' ||
    !values(v, ['income_total', 'expense_total', 'cash_balance'])) return false
  const summary = v.budget_summary
  return record(summary) && period(summary) && summary.year === v.year && summary.month === v.month &&
    summary.currency === 'BRL' && values(summary, ['planned', 'actual', 'balance']) &&
    (summary.utilization_percentage === null || money(summary.utilization_percentage)) &&
    Array.isArray(v.monthly) && v.monthly.length > 0 && v.monthly.length <= 24 &&
    v.monthly.every((item) => record(item) && period(item) && counts(item) && values(item, ['income', 'expenses', 'balance'])) &&
    Array.isArray(v.categories) && v.categories.every((item) => record(item) && integer(item.category_id) && item.category_id > 0 &&
      typeof item.category_name === 'string' && values(item, ['planned', 'actual', 'balance', 'expense_share_percentage'])) &&
    Array.isArray(v.campaigns) && v.campaigns.every((item) => record(item) &&
      (item.campaign_id === null || (integer(item.campaign_id) && item.campaign_id > 0)) &&
      typeof item.campaign_name === 'string' && counts(item) && values(item, ['income', 'expenses', 'balance']))
}

export async function getDashboardAnalytics(
  year: number, month: number, months: number, signal: AbortSignal,
): Promise<DashboardAnalytics> {
  const baseUrl = getApiBaseUrl()
  if (!baseUrl) throw new Error('O endereço da API não foi configurado.')
  const params = new URLSearchParams({ year: String(year), month: String(month), months: String(months) })
  const response = await authFetch(`${baseUrl.replace(/\/$/, '')}/dashboard/analytics?${params}`, { signal })
  if (!response.ok) throw new Error(`Não foi possível consultar o dashboard (HTTP ${response.status}). Verifique o backend e as migrações.`)
  const data: unknown = await response.json()
  if (!isAnalytics(data) || data.year !== year || data.month !== month) {
    throw new Error('A API retornou dados em formato ou período inesperado.')
  }
  const lastMonth = data.monthly[data.monthly.length - 1]
  if (lastMonth.year !== year || lastMonth.month !== month || data.monthly.length > months) {
    throw new Error('A API retornou um histórico em período inesperado.')
  }
  return data
}
