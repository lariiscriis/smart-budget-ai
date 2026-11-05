import { isPositiveId, isRecord, requestRecord } from './recordsApi'
import { validateDate } from '../utils/entryForm'
import type { AttributedRecord } from './attribution'

export type IncomeInput = {
  category_id: number; campaign_id?: number | null
  description: string; income_date: string; amount: string
}
export type Income = IncomeInput & AttributedRecord & { id: number; campaign_id: number | null }

function isIncome(value: unknown): value is Income {
  if (!isRecord(value) || !isPositiveId(value.id) || !isPositiveId(value.category_id) ||
    !(value.campaign_id === null || isPositiveId(value.campaign_id)) ||
    typeof value.description !== 'string' || typeof value.income_date !== 'string' ||
    typeof value.amount !== 'string' || !/^\d+(\.\d{1,2})?$/.test(value.amount) || !/[1-9]/.test(value.amount)) return false
  try { validateDate(value.income_date); return true } catch { return false }
}

export async function createIncome(payload: IncomeInput): Promise<Income> {
  const data = await requestRecord('/incomes', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  }, {
    404: 'Categoria ou campanha não encontrada. Atualize as listas.',
    409: 'A categoria ou campanha deixou de estar disponível. Atualize as listas.',
    422: 'Dados inválidos. Use uma categoria de receita e valor positivo com até duas casas decimais.',
  })
  if (!isIncome(data)) throw new Error('A resposta do cadastro da receita veio em formato inesperado.')
  return data
}

export async function listIncomes(year: number, month: number, offset = 0, limit = 20): Promise<Income[]> {
  const params = new URLSearchParams({ year: String(year), month: String(month), offset: String(offset), limit: String(limit) })
  const data = await requestRecord(`/incomes?${params}`)
  if (!Array.isArray(data) || !data.every(isIncome)) throw new Error('A API retornou receitas em formato inesperado.')
  return data
}
