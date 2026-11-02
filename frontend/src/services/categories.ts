export type Category = {
  id: number
  name: string
}

function getBaseUrl(): string {
  const value = import.meta.env.VITE_API_BASE_URL

  if (!value) {
    throw new Error('O endereço da API não foi configurado.')
  }

  return value
}

function isCategory(value: unknown): value is Category {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  const data = value as Record<string, unknown>

  return (
    typeof data.id === 'number' &&
    Number.isInteger(data.id) &&
    data.id > 0 &&
    typeof data.name === 'string'
  )
}

export async function listCategories(
  offset = 0,
  limit = 20,
): Promise<Category[]> {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  })

  const response = await fetch(`${getBaseUrl()}/categories?${params}`)

  if (!response.ok) {
    throw new Error(`Falha ao consultar categorias: HTTP ${response.status}.`)
  }

  const data: unknown = await response.json()

  if (!Array.isArray(data) || !data.every(isCategory)) {
    throw new Error('A API retornou categorias em formato inesperado.')
  }

  return data
}

export async function createCategory(name: string): Promise<Category> {
  const response = await fetch(`${getBaseUrl()}/categories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })

  if (response.status === 409) {
    throw new Error('Já existe uma categoria com esse nome.')
  }

  if (response.status === 422) {
    throw new Error('Informe um nome válido com até 100 caracteres.')
  }

  if (!response.ok) {
    throw new Error(`Falha ao cadastrar categoria: HTTP ${response.status}.`)
  }

  const data: unknown = await response.json()

  if (!isCategory(data)) {
    throw new Error('A resposta do cadastro veio em formato inesperado.')
  }

  return data
}