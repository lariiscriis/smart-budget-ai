import { authFetch, getApiBaseUrl } from './http'

type ValidRow = {
  row: number
  data: {
    category_id: number
    description: string
    expense_date: string
    amount: string
  }
}

export type ImportBatch = {
  import_id: string
  filename: string
  status: 'pending' | 'completed'
  saved_count: number
  report: {
    total_rows: number
    valid_count: number
    invalid_count: number
    duplicate_count: number
    valid_rows: ValidRow[]
    errors: { row: number; messages: string[] }[]
    duplicates: { row: number; same_as_row: number; message: string }[]
  }
}

export type ImportHistoryItem = Pick<
  ImportBatch,
  'import_id' | 'filename' | 'status' | 'saved_count'
>

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const baseUrl = getApiBaseUrl()

  if (!baseUrl) {
    throw new Error('O endereço da API não foi configurado.')
  }

  const response = await authFetch(`${baseUrl}${path}`, options)
  const data: unknown = await response.json()

  if (!response.ok) {
    const detail =
      typeof data === 'object' &&
      data !== null &&
      'detail' in data &&
      typeof data.detail === 'string'
        ? data.detail
        : `Falha na operação: HTTP ${response.status}.`

    throw new Error(detail)
  }

  return data as T
}

export function previewImport(file: File): Promise<ImportBatch> {
  const body = new FormData()
  body.append('file', file)

  return request<ImportBatch>('/imports/expenses/preview', {
    method: 'POST',
    body,
  })
}

export function getImport(id: string): Promise<ImportBatch> {
  return request<ImportBatch>(`/imports/${encodeURIComponent(id)}`)
}

export function listImports(): Promise<ImportHistoryItem[]> {
  return request<ImportHistoryItem[]>('/imports?limit=20')
}

export async function confirmImport(
  id: string,
  acceptValidOnly: boolean,
): Promise<void> {
  await request<unknown>(`/imports/${encodeURIComponent(id)}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ accept_valid_only: acceptValidOnly }),
  })
}
