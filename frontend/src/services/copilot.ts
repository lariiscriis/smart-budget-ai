import type { FinancialSummary } from './api'
import { authFetch, getApiBaseUrl } from './http'

export type CopilotAlert = {
  category_id: number
  category_name: string
  code: 'unbudgeted' | 'over_budget' | 'near_limit'
  severity: 'warning' | 'critical'
  message: string
  planned: string
  actual: string
  balance: string
}

export type PolicySource = {
  source_id: string
  document_id: string
  version: string
  section_id: string
  section_title: string
  text: string
  similarity: number
}

export type CopilotResponse = {
  mode: 'mock' | 'gemini'
  answer: string
  tools_used: {
    name: string
    arguments: {
      year: number
      month: number
    }
    result: FinancialSummary | null
    sources: PolicySource[]
    cited_source_ids: string[]
    alerts: CopilotAlert[]
    categories?: {
      category_id: number
      category_name: string
      summary: FinancialSummary
    }[]
    
  }[]
}

export async function askCopilot(
  question: string,
  year: number,
  month: number,
): Promise<CopilotResponse> {
  const baseUrl = getApiBaseUrl()

  if (!baseUrl) {
    throw new Error('O endereço da API não foi configurado.')
  }

  const response = await authFetch(`${baseUrl}/copilot/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, year, month }),
  })

  const data: unknown = await response.json()

  if (!response.ok) {
    const detail =
      typeof data === 'object' &&
      data !== null &&
      'detail' in data &&
      typeof data.detail === 'string'
        ? data.detail
        : `Falha na consulta: HTTP ${response.status}.`

    throw new Error(detail)
  }

  return data as CopilotResponse
}
