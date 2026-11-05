import { authFetch, getApiBaseUrl } from './http'

/** JSON boundary shared by financial entry and campaign services. */
export async function requestRecord(
  path: string,
  options?: RequestInit,
  messages: Record<number, string> = {},
): Promise<unknown> {
  const baseUrl = getApiBaseUrl()
  if (!baseUrl) throw new Error('O endereço da API não foi configurado.')
  const response = await authFetch(`${baseUrl.replace(/\/$/, '')}${path}`, options)
  let data: unknown
  try { data = await response.json() } catch {
    if (response.ok) throw new Error('A API retornou uma resposta em formato inesperado.')
  }
  if (!response.ok) {
    const detail = isRecord(data) && typeof data.detail === 'string' ? data.detail : null
    throw new Error(detail ?? messages[response.status] ?? `Não foi possível concluir a operação: HTTP ${response.status}.`)
  }
  return data
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

export function isPositiveId(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0
}
