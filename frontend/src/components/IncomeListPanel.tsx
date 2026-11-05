import { useEffect, useState } from 'react'
import { listIncomes } from '../services/incomes'
import type { Income } from '../services/incomes'
import { listAllCategories } from '../services/categories'
import { listAllCampaigns } from '../services/campaigns'
import { parsePeriod } from '../utils/entryForm'
import { formatMoney } from '../utils/format'
import RecordAttribution from './RecordAttribution'

const PAGE_SIZE = 20

export default function IncomeListPanel({ period, onPeriodChange, refresh }: {
  period: string; onPeriodChange: (value: string) => void; refresh: number
}) {
  const [incomes, setIncomes] = useState<Income[]>([])
  const [offset, setOffset] = useState(0)
  const [reload, setReload] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [categoryNames, setCategoryNames] = useState<Record<number, string>>({})
  const [campaignNames, setCampaignNames] = useState<Record<number, string>>({})
  const [namesWarning, setNamesWarning] = useState(false)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const { year, month } = parsePeriod(period)
        const [rows, categories, campaigns] = await Promise.all([
          listIncomes(year, month, offset, PAGE_SIZE),
          listAllCategories('income').then((data) => ({ data, ok: true })).catch(() => ({ data: [], ok: false })),
          listAllCampaigns().then((data) => ({ data, ok: true })).catch(() => ({ data: [], ok: false })),
        ])
        if (active) {
          setIncomes(rows)
          setCategoryNames(Object.fromEntries(categories.data.map((item) => [item.id, item.name])))
          setCampaignNames(Object.fromEntries(campaigns.data.map((item) => [item.id, item.name])))
          setNamesWarning(!categories.ok || !campaigns.ok)
        }
      } catch (err: unknown) {
        if (active) setError(err instanceof Error ? err.message : 'Não foi possível consultar as receitas.')
      } finally { if (active) setLoading(false) }
    }
    void load()
    return () => { active = false }
  }, [period, refresh, offset, reload])

  return <section className="entry-panel" aria-labelledby="income-list-heading">
    <h2 id="income-list-heading">Receitas cadastradas</h2>
    <p>Consulte as receitas do mês. Para cadastrar, escolha Receita realizada em Novo lançamento.</p>
    <div className="period-form">
      <div><label htmlFor="income-list-period">Mês das receitas</label>
        <input id="income-list-period" type="month" min="2000-01" max="2100-12" required value={period} disabled={loading}
          onChange={(event) => { if (event.target.value) { onPeriodChange(event.target.value); setOffset(0) } }} />
      </div>
      <button className="secondary-button" type="button" disabled={loading} onClick={() => { setOffset(0); setReload((value) => value + 1) }}>Consultar / atualizar receitas</button>
    </div>
    {loading && <p role="status">Consultando receitas...</p>}
    {error && <p className="error-message" role="alert">{error}</p>}
    {!loading && !error && <>
      {namesWarning && <p role="status">Alguns nomes não puderam ser consultados. Os registros continuam identificados pelos IDs.</p>}
      <p>Página {offset / PAGE_SIZE + 1} · {period.split('-').reverse().join('/')}</p>
      {incomes.length === 0 ? <p>Nenhuma receita nesta página para o mês selecionado.</p> : <div className="table-scroll"><table>
        <caption>Receitas registradas no mês selecionado</caption>
        <thead><tr><th scope="col">ID</th><th scope="col">Data</th><th scope="col">Descrição</th><th scope="col">Categoria</th><th scope="col">Campanha</th><th scope="col">Valor</th><th scope="col">Autoria</th></tr></thead>
        <tbody>{incomes.map((item) => <tr key={item.id}>
          <td>{item.id}</td><td>{item.income_date.split('-').reverse().join('/')}</td><td>{item.description}</td>
          <td>{categoryNames[item.category_id] ?? `Categoria #${item.category_id}`}</td>
          <td>{item.campaign_id === null ? 'Sem campanha' : campaignNames[item.campaign_id] ?? `Campanha #${item.campaign_id}`}</td>
          <td>{formatMoney(item.amount)}</td>
          <td><RecordAttribution record={item} /></td>
        </tr>)}</tbody>
      </table></div>}
    </>}
    <div className="pagination">
      <button className="secondary-button" type="button" disabled={loading || offset === 0} onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}>Anterior</button>
      <button className="secondary-button" type="button" disabled={loading || Boolean(error) || incomes.length < PAGE_SIZE} onClick={() => setOffset((value) => value + PAGE_SIZE)}>Próxima</button>
    </div>
  </section>
}
