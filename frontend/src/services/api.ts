import { authFetch, getApiBaseUrl } from './http'

export type FinancialSummary = {
  year: number
  month: number
  currency: string
  planned: string
  actual: string
  balance: string
  utilization_percentage: string | null
}

function isDecimal(value: unknown): value is string {
  return typeof value === 'string' && /^-?\d+(\.\d{1,2})?$/.test(value)
}

function isFinancialSummary(value: unknown): value is FinancialSummary {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  const data = value as Record<string, unknown>

  return (
    Number.isInteger(data.year) &&
    Number.isInteger(data.month) &&
    data.currency === 'BRL' &&
    isDecimal(data.planned) &&
    isDecimal(data.actual) &&
    isDecimal(data.balance) &&
    (
      data.utilization_percentage === null ||
      isDecimal(data.utilization_percentage)
    )
  )
}

export async function getFinancialSummary(
  year: number,
  month: number,
): Promise<FinancialSummary> {
  const baseUrl = getApiBaseUrl()

  if (!baseUrl) {
    throw new Error('O endereço da API não foi configurado.')
  }

  const params = new URLSearchParams({
    year: String(year),
    month: String(month),
  })

  const response = await authFetch(
    `${baseUrl}/dashboard/summary?${params}`,
  )

  if (!response.ok) {
    throw new Error(`Não foi possível consultar o resumo: HTTP ${response.status}.`)
  }

  const data: unknown = await response.json()

  if (!isFinancialSummary(data)) {
    throw new Error('A API retornou um resumo em formato inesperado.')
  }

  if (data.year !== year || data.month !== month) {
    throw new Error('A API retornou um período diferente do solicitado.')
  }

  return data
}
