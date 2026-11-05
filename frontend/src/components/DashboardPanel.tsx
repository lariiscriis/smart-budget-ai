import { useEffect, useState } from 'react'
import { getDashboardAnalytics } from '../services/dashboard'
import type { DashboardAnalytics } from '../services/dashboard'
import { ChartLegend, HorizontalBars, MonthlyChart } from './FinancialCharts'
import { formatMoney, monthLabel } from '../utils/format'

export default function DashboardPanel({ period }: { period: string }) {
  const [months, setMonths] = useState(12)
  const [reload, setReload] = useState(0)
  const [data, setData] = useState<DashboardAnalytics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [year, month] = period.split('-').map(Number)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    let timedOut = false
    const timeout = setTimeout(() => { timedOut = true; controller.abort() }, 20000)
    async function load() {
      setLoading(true)
      setError(null)
      setData(null)
      try {
        const result = await getDashboardAnalytics(year, month, months, controller.signal)
        if (active) setData(result)
      } catch (err: unknown) {
        if (active) setError(timedOut ? 'A consulta demorou mais que o esperado. Tente novamente.' : err instanceof Error ? err.message : 'Não foi possível carregar os dados.')
      } finally {
        clearTimeout(timeout)
        if (active) setLoading(false)
      }
    }
    void load()
    return () => { active = false; clearTimeout(timeout); controller.abort() }
  }, [year, month, months, reload])

  const expenses = data?.categories.filter((item) => Number(item.actual) > 0) ?? []
  const hasHistory = data?.monthly.some((item) => item.income_count > 0 || item.expense_count > 0)

  return <div className="analytics" aria-busy={loading}>
    <div className="dashboard-toolbar">
      <p>Indicadores do mês selecionado. A evolução inclui os meses anteriores.</p>
      <button className="secondary-button" type="button" disabled={loading} onClick={() => setReload((value) => value + 1)}>Atualizar dados</button>
    </div>
    {loading && <p className="dashboard-status" role="status">Consultando os registros financeiros…</p>}
    {error && <p className="error-message" role="alert">{error}</p>}
    {data && <>
      <dl className="metrics" aria-label="Indicadores do mês">
        <div className="metric"><dt>Receitas</dt><dd>{formatMoney(data.income_total)}</dd></div>
        <div className="metric"><dt>Despesas</dt><dd>{formatMoney(data.expense_total)}</dd></div>
        <div className="metric"><dt>Resultado do mês</dt><dd className={data.cash_balance.startsWith('-') ? 'negative' : ''}>{formatMoney(data.cash_balance)}</dd></div>
        <div className="metric"><dt>Orçamento previsto</dt><dd>{formatMoney(data.budget_summary.planned)}</dd></div>
      </dl>
      <div className="budget-note">
        <span>Saldo do orçamento: <strong>{formatMoney(data.budget_summary.balance)}</strong></span>
        <span>Utilização: <strong>{data.budget_summary.utilization_percentage === null ? 'Não se aplica' : `${data.budget_summary.utilization_percentage.replace('.', ',')}%`}</strong></span>
      </div>
      <p className="data-note">Resultado do mês = receitas − despesas registradas. Não representa saldo bancário nem lucro contábil.</p>

      <section className="chart-section" aria-labelledby="monthly-title">
        <div className="section-heading"><div><p className="eyebrow">01 / Fluxo financeiro</p><h2 id="monthly-title">Receitas e despesas ao longo do tempo</h2></div>
          <label className="history-select">Histórico<select value={months} onChange={(event) => setMonths(Number(event.target.value))}>
            <option value={6}>6 meses</option><option value={12}>12 meses</option><option value={24}>24 meses</option>
          </select></label>
        </div>
        <p className="section-description">De {monthLabel(data.monthly[0].year, data.monthly[0].month)} a {monthLabel(data.year, data.month)}. Meses sem lançamentos têm total zero.</p>
        <ChartLegend />
        {hasHistory ? <MonthlyChart data={data.monthly} /> : <p className="empty-state">Nenhuma receita ou despesa registrada neste intervalo.</p>}
        <details className="chart-data"><summary>Ver dados mensais</summary><div className="table-scroll"><table><caption>Valores em reais por mês</caption><thead><tr><th scope="col">Mês</th><th scope="col">Receitas</th><th scope="col">Despesas</th><th scope="col">Resultado</th></tr></thead>
          <tbody>{data.monthly.map((item) => <tr key={`${item.year}-${item.month}`}><th scope="row">{monthLabel(item.year, item.month)}</th><td>{formatMoney(item.income)}</td><td>{formatMoney(item.expenses)}</td><td>{formatMoney(item.balance)}</td></tr>)}</tbody></table></div></details>
      </section>

      <section className="chart-section" aria-labelledby="expense-category-title">
        <div className="section-heading"><div><p className="eyebrow">02 / Composição das despesas</p><h2 id="expense-category-title">Onde os recursos foram utilizados</h2></div><span className="period-tag">{monthLabel(data.year, data.month)}</span></div>
        <p className="section-description">Despesas por categoria, da maior para a menor. A participação é calculada sobre as despesas do mês.</p>
        {expenses.length ? <HorizontalBars firstLabel="Despesas" rows={expenses.map((item) => ({ id: String(item.category_id), label: item.category_name, first: item.actual, note: `${item.expense_share_percentage.replace('.', ',')}% do total` }))} /> : <p className="empty-state">Nenhuma despesa registrada neste mês.</p>}
      </section>

      <section className="chart-section" aria-labelledby="budget-category-title">
        <div className="section-heading"><div><p className="eyebrow">03 / Acompanhamento do orçamento</p><h2 id="budget-category-title">Previsto e realizado por categoria</h2></div><span className="period-tag">{monthLabel(data.year, data.month)}</span></div>
        <p className="section-description">Inclui categorias com despesas sem orçamento e orçamentos ainda não utilizados.</p><ChartLegend budget />
        {data.categories.length ? <>
          <HorizontalBars firstLabel="Previsto" secondLabel="Realizado" rows={data.categories.map((item) => ({ id: String(item.category_id), label: item.category_name, first: item.planned, second: item.actual }))} />
          <details className="chart-data"><summary>Ver saldos por categoria</summary><div className="table-scroll"><table><caption>Comparação de orçamento em reais</caption><thead><tr><th scope="col">Categoria</th><th scope="col">Previsto</th><th scope="col">Realizado</th><th scope="col">Saldo</th></tr></thead><tbody>{data.categories.map((item) => <tr key={item.category_id}><th scope="row">{item.category_name}</th><td>{formatMoney(item.planned)}</td><td>{formatMoney(item.actual)}</td><td>{formatMoney(item.balance)}</td></tr>)}</tbody></table></div></details>
        </> : <p className="empty-state">Nenhum orçamento ou despesa registrado neste mês.</p>}
      </section>

      <section className="chart-section" aria-labelledby="campaign-title">
        <div className="section-heading"><div><p className="eyebrow">04 / Campanhas</p><h2 id="campaign-title">Custo e receitas vinculadas</h2></div><span className="period-tag">{monthLabel(data.year, data.month)}</span></div>
        <p className="section-description">Compara os valores registrados para cada campanha no mês. A vinculação não comprova que a campanha causou a receita.</p><ChartLegend />
        {data.campaigns.length ? <>
          <HorizontalBars firstLabel="Receitas" secondLabel="Despesas" rows={data.campaigns.map((item) => ({ id: item.campaign_id === null ? 'unassigned' : String(item.campaign_id), label: item.campaign_name, first: item.income, second: item.expenses }))} />
          <details className="chart-data"><summary>Ver resultados por campanha</summary><div className="table-scroll"><table><caption>Valores vinculados em reais; resultado = receitas − despesas</caption><thead><tr><th scope="col">Campanha</th><th scope="col">Receitas</th><th scope="col">Despesas</th><th scope="col">Resultado</th></tr></thead><tbody>{data.campaigns.map((item) => <tr key={item.campaign_id ?? 'unassigned'}><th scope="row">{item.campaign_name}</th><td>{formatMoney(item.income)}</td><td>{formatMoney(item.expenses)}</td><td>{formatMoney(item.balance)}</td></tr>)}</tbody></table></div></details>
        </> : <p className="empty-state">Nenhuma receita ou despesa registrada neste mês. Campanhas sem movimentação não aparecem.</p>}
        <p className="data-note">“Sem campanha” reúne lançamentos sem vínculo, incluindo importações antigas. O resultado considera somente os valores cadastrados.</p>
      </section>
    </>}
  </div>
}
