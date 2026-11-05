import { useState } from 'react'
import { listAllCampaigns } from '../services/campaigns'
import type { Campaign } from '../services/campaigns'

export default function CampaignSelect({ value, onChange, disabled }: {
  value: string; onChange: (value: string) => void; disabled: boolean
}) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)

  async function load() {
    if (loading || disabled) return
    setLoading(true)
    setError(null)
    try {
      const all = await listAllCampaigns()
      setCampaigns(all)
      setLoaded(true)
      if (value && !all.some((item) => String(item.id) === value)) {
        onChange('')
        setError('A campanha selecionada não está mais disponível. Selecione outra ou mantenha sem campanha.')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Não foi possível consultar as campanhas.')
    } finally { setLoading(false) }
  }

  return <div>
    <label>Campanha (opcional)
      <select value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled || loading}>
        <option value="">Sem campanha</option>
        {campaigns.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </label>
    <button className="secondary-button" type="button" disabled={disabled || loading} onClick={() => void load()}>
      {loading ? 'Consultando campanhas...' : 'Carregar / atualizar campanhas'}
    </button>
    {loaded && campaigns.length === 0 && <p role="status">Nenhuma campanha cadastrada. O vínculo é opcional.</p>}
    {error && <p className="error-message" role="alert">{error} Você pode salvar sem campanha.</p>}
  </div>
}
