export type BudgetInput = {
  category_id: number
  year: number
  month: number
  amount: string
}

export type ExpenseInput = {
  category_id: number
  description: string
  expense_date: string
  amount: string
}

async function postEntry(
  path: string,
  payload: BudgetInput | ExpenseInput,
): Promise<void> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL

  if (!baseUrl) {
    throw new Error('O endereço da API não foi configurado.')
  }

  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (response.status === 404) {
    throw new Error('Categoria não encontrada. Atualize as categorias.')
  }

  if (response.status === 409) {
    throw new Error(
      'Conflito no cadastro. Para orçamento, confira se já existe valor para essa categoria e período.',
    )
  }

  if (response.status === 422) {
    throw new Error('Dados inválidos. Confira os campos e o limite de duas casas decimais.')
  }

  if (!response.ok) {
    throw new Error(`Não foi possível salvar: HTTP ${response.status}.`)
  }
}

export function createBudget(payload: BudgetInput): Promise<void> {
  return postEntry('/budgets', payload)
}

export function createExpense(payload: ExpenseInput): Promise<void> {
  return postEntry('/expenses', payload)
}