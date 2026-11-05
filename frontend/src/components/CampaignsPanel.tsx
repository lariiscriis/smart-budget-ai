import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { createCampaign, listCampaigns } from '../services/campaigns'
import type { Campaign } from '../services/campaigns'
import RecordAttribution from './RecordAttribution'

const PAGE_SIZE = 20

export default function CampaignsPanel() {
  const [name, setName] = useState('')
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [offset, setOffset] = useState(0)
  const [reload, setReload] = useState(0)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [listError, setListError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const busy = loading || creating

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setListError(null)
      try {
        const page = await listCampaigns(offset, PAGE_SIZE)
        if (active) setCampaigns(page)
      } catch (err: unknown) {
        if (active) setListError(err instanceof Error ? err.message : 'Não foi possível consultar as campanhas.')
      } finally { if (active) setLoading(false) }
    }
    void load()
    return () => { active = false }
  }, [offset, reload])

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setError(null)
    setSuccess(null)
    const cleaned = name.trim()
    if (!cleaned || cleaned.length > 100) {
      setError('Informe um nome válido com até 100 caracteres.')
      return
    }
    setCreating(true)
    try {
      const created = await createCampaign(cleaned)
      setName('')
      setSuccess(`Campanha "${created.name}" cadastrada. Use Carregar / atualizar campanhas no lançamento para selecioná-la.`)
      setOffset(0)
      setReload((value) => value + 1)
    } catch (err: unknown) {
      setError(`${err instanceof Error ? err.message : 'Não foi possível cadastrar a campanha.'} Se houve falha de conexão, consulte a lista antes de repetir o cadastro.`)
    } finally { setCreating(false) }
  }

  return <section className="categories-panel" aria-labelledby="campaigns-heading">
    <h2 id="campaigns-heading">Campanhas</h2>
    <p>Cadastre campanhas para vincular receitas e despesas.</p>
    <form className="period-form" onSubmit={handleCreate}>
      <div><label htmlFor="campaign-name">Nome da campanha</label>
        <input id="campaign-name" required maxLength={100} value={name} disabled={busy} onChange={(event) => setName(event.target.value)} />
      </div>
      <button type="submit" disabled={busy}>{creating ? 'Cadastrando...' : 'Cadastrar campanha'}</button>
    </form>
    {error && <p className="error-message" role="alert">{error}</p>}
    {success && <p className="success-message" role="status">{success}</p>}
    <button className="secondary-button" type="button" disabled={busy} onClick={() => setReload((value) => value + 1)}>Atualizar lista de campanhas</button>
    {loading && <p role="status">Consultando campanhas...</p>}
    {listError && <p className="error-message" role="alert">{listError}</p>}
    {!loading && !listError && <>
      <p>Página {offset / PAGE_SIZE + 1}</p>
      {campaigns.length === 0 ? <p>Nenhuma campanha nesta página.</p> : <ul className="category-list">
        {campaigns.map((item) => <li key={item.id}><strong>{item.name}</strong><small>ID: {item.id}</small><RecordAttribution record={item} /></li>)}
      </ul>}
    </>}
    <div className="pagination">
      <button className="secondary-button" type="button" disabled={busy || offset === 0} onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}>Anterior</button>
      <button className="secondary-button" type="button" disabled={busy || Boolean(listError) || campaigns.length < PAGE_SIZE} onClick={() => setOffset((value) => value + PAGE_SIZE)}>Próxima</button>
    </div>
  </section>
}
