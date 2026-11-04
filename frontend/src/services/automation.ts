export type FinancialAlert = {
  category_id: number
  category_name: string
  code: 'unbudgeted' | 'over_budget' | 'near_limit'
  severity: 'warning' | 'critical'
  message: string
  planned: string
  actual: string
  balance: string
}

export type AlertsResponse = {
  year: number
  month: number
  rules_version: string
  count: number
  alerts: FinancialAlert[]
}

export type AutomationJob = {
  id: number
  import_id: string
  year: number
  month: number
  status: 'pending' | 'running' | 'succeeded' | 'failed'
  attempts: number
  last_error: string | null
  result: unknown
  created_at: string
}

const API_URL = (
  import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'
).replace(/\/$/, '')

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, options)

  if (!response.ok) {
    if (response.status === 409) {
      throw new Error(
        'A tarefa mudou de estado e não pode ser reenfileirada. Atualize o histórico.',
      )
    }

    throw new Error(`A API retornou um erro (${response.status}).`)
  }

  return response.json() as Promise<T>
}

export function getAlerts(
  year: number,
  month: number,
): Promise<AlertsResponse> {
  const params = new URLSearchParams({
    year: String(year),
    month: String(month),
  })

  return request<AlertsResponse>(`/alerts?${params}`)
}

export function getAutomationJobs(): Promise<AutomationJob[]> {
  return request<AutomationJob[]>('/automations?offset=0&limit=20')
}

export function retryAutomationJob(
  jobId: number,
): Promise<AutomationJob> {
  return request<AutomationJob>(`/automations/${jobId}/retry`, {
    method: 'POST',
  })
}