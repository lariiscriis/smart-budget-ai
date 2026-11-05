import { authFetch, getApiBaseUrl } from './http'
import type { AttributedRecord } from './attribution'

export type CategoryType = 'income' | 'expense'

export type Category = AttributedRecord & {
  id: number
  name: string
  type: CategoryType
}

function getBaseUrl(): string {
  const value = getApiBaseUrl()

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
    typeof data.name === 'string' &&
    (data.type === 'income' || data.type === 'expense')
  )
}

export async function listCategories(
  offset = 0,
  limit = 20,
  type?: CategoryType,
): Promise<Category[]> {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  })
  if (type) params.set('type', type)

  const response = await authFetch(`${getBaseUrl()}/categories?${params}`)

  if (!response.ok) {
    throw new Error(`Falha ao consultar categorias: HTTP ${response.status}.`)
  }

  const data: unknown = await response.json()

  if (!Array.isArray(data) || !data.every(isCategory)) {
    throw new Error('A API retornou categorias em formato inesperado.')
  }

  return data
}

export async function createCategory(name: string, type: CategoryType): Promise<Category> {
  const response = await authFetch(`${getBaseUrl()}/categories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, type }),
  })

  if (response.status === 409) {
    throw new Error('Já existe uma categoria com esse nome e tipo.')
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

export async function listAllCategories(type: CategoryType): Promise<Category[]> {
  const all: Category[] = []
  for (let offset = 0; ; offset += 100) {
    const page = await listCategories(offset, 100, type)
    all.push(...page.filter((category) => category.type === type))
    if (page.length < 100) return all
  }
}
