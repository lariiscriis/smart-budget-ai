import { requestRecord } from './recordsApi'

export type BudgetInput = {
  category_id: number
  year: number
  month: number
  amount: string
}

export type ExpenseInput = {
  category_id: number
  campaign_id?: number | null
  description: string
  expense_date: string
  amount: string
}

async function postEntry(
  path: string,
  payload: BudgetInput | ExpenseInput,
): Promise<void> {
  await requestRecord(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, {
    404: 'Categoria ou campanha não encontrada. Atualize as listas.',
    409: 'Conflito no cadastro. Para orçamento, confira se já existe valor para essa categoria e período.',
    422: 'Dados inválidos. Confira o tipo da categoria, os campos e o limite de duas casas decimais.',
  })
}

export function createBudget(payload: BudgetInput): Promise<void> {
  return postEntry('/budgets', payload)
}

export function createExpense(payload: ExpenseInput): Promise<void> {
  return postEntry('/expenses', payload)
}
