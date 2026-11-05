import { isPositiveId, isRecord, requestRecord } from './recordsApi'
import type { AttributedRecord } from './attribution'

export type Campaign = AttributedRecord & { id: number; name: string }

function isCampaign(value: unknown): value is Campaign {
  return isRecord(value) && isPositiveId(value.id) && typeof value.name === 'string'
}

export async function listCampaigns(offset = 0, limit = 20): Promise<Campaign[]> {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) })
  const data = await requestRecord(`/campaigns?${params}`)
  if (!Array.isArray(data) || !data.every(isCampaign)) throw new Error('A API retornou campanhas em formato inesperado.')
  return data
}

export async function listAllCampaigns(): Promise<Campaign[]> {
  const all: Campaign[] = []
  for (let offset = 0; ; offset += 100) {
    const page = await listCampaigns(offset, 100)
    all.push(...page)
    if (page.length < 100) return all
  }
}

export async function createCampaign(name: string): Promise<Campaign> {
  const data = await requestRecord('/campaigns', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
  }, { 409: 'Já existe uma campanha com esse nome.', 422: 'Informe um nome válido com até 100 caracteres.' })
  if (!isCampaign(data)) throw new Error('A resposta do cadastro da campanha veio em formato inesperado.')
  return data
}
