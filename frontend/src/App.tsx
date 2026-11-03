import { useState } from 'react'
import type { FormEvent } from 'react'
import CategoriesPanel from './components/CategoriesPanel'
import { getFinancialSummary } from './services/api'
import type { FinancialSummary } from './services/api'
import './App.css'
import FinancialEntryPanel from './components/FinancialEntryPanel'
import ImportPanel from './components/ImportPanel'

function getInitialPeriod() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function formatMoney(value: string) {
  const negative = value.startsWith('-')
  const unsigned = negative ? value.slice(1) : value
  const [integer, fraction = ''] = unsigned.split('.')
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, '.')

  return `${negative ? '-' : ''}R$ ${grouped},${fraction.padEnd(2, '0')}`
}

function App() {
  const [period, setPeriod] = useState(getInitialPeriod)
  const [summary, setSummary] = useState<FinancialSummary | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadSummary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (isLoading) return

    setIsLoading(true)
    setError(null)
    setSummary(null)

    try {
      const [year, month] = period.split('-').map(Number)
      const result = await getFinancialSummary(year, month)
      setSummary(result)
    } catch (error: unknown) {
      setError(
        error instanceof Error
          ? error.message
          : 'Ocorreu um erro inesperado.',
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="dashboard">
      <header>
        <p className="eyebrow">SMART BUDGET AI</p>
        <h1>Visão financeira</h1>
        <p>Consulte o orçamento e as despesas do período.</p>
      </header>

      <form className="period-form" onSubmit={loadSummary}>
        <div>
          <label htmlFor="period">Mês de referência</label>
          <input
            id="period"
            type="month"
            min="2000-01"
            max="2100-12"
            required
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
            disabled={isLoading}
          />
        </div>

        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Consultando...' : 'Consultar período'}
        </button>
      </form>

      {isLoading && <p role="status">Carregando indicadores...</p>}

      {error && (
        <p className="error-message" role="alert">
          {error} Confira se o backend está disponível e tente novamente.
        </p>
      )}

      {!summary && !isLoading && !error && (
        <p role="status">Selecione um período e clique em consultar.</p>
      )}

      {summary && (
        <section aria-labelledby="summary-heading">
          <h2 id="summary-heading">
            Resumo de {String(summary.month).padStart(2, '0')}/{summary.year}
          </h2>

          <div className="metrics">
            <article className="metric">
              <h3>Previsto</h3>
              <p>{formatMoney(summary.planned)}</p>
            </article>

            <article className="metric">
              <h3>Realizado</h3>
              <p>{formatMoney(summary.actual)}</p>
            </article>

            <article className="metric">
              <h3>Saldo</h3>
              <p className={summary.balance.startsWith('-') ? 'negative' : ''}>
                {formatMoney(summary.balance)}
              </p>
            </article>

            <article className="metric">
              <h3>Utilização</h3>
              <p>
                {summary.utilization_percentage === null
                  ? 'Não se aplica'
                  : `${summary.utilization_percentage.replace('.', ',')}%`}
              </p>
            </article>
          </div>

          {summary.utilization_percentage === null && (
            <p>Não há valor previsto positivo para calcular a utilização.</p>
          )}
        </section>
      )}
      <ImportPanel />
      <FinancialEntryPanel />
      <CategoriesPanel />
    </main>
  )
}


export default App