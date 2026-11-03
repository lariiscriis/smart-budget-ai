import type { FinancialSummary } from './api'

export type CopilotResponse = {
  mode: 'mock' | 'gemini'
  answer: string
  tools_used: {
    name: string
    arguments: {
      year: number
      month: number
    }
    result: FinancialSummary

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
  const baseUrl = import.meta.env.VITE_API_BASE_URL

  if (!baseUrl) {
    throw new Error('O endereço da API não foi configurado.')
  }

  const response = await fetch(`${baseUrl}/copilot/chat`, {
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