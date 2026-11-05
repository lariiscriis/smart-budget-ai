import { useState } from 'react'
import type { FormEvent } from 'react'

import { askCopilot } from '../services/copilot'
import type { CopilotResponse } from '../services/copilot'

function initialPeriod() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

type Answer = {
  question: string
  period: string
  response: CopilotResponse
}

export default function CopilotPanel() {
  const [period, setPeriod] = useState(initialPeriod)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (busy) return

    const cleanedQuestion = question.trim()

    if (!cleanedQuestion) {
      setError('Escreva uma pergunta.')
      return
    }

    setBusy(true)
    setError(null)
    setAnswer(null)

    try {
      const [year, month] = period.split('-').map(Number)
      const response = await askCopilot(cleanedQuestion, year, month)

      setAnswer({
        question: cleanedQuestion,
        period,
        response,
      })
    } catch (error: unknown) {
      setError(
        error instanceof Error ? error.message : 'Erro inesperado.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="copilot-panel" aria-labelledby="copilot-heading">
      <p className="eyebrow">ASSISTENTE FINANCEIRO</p>
      <h2 id="copilot-heading">Copiloto Smart Budget</h2>
      <p>
        Consulte dados financeiros do período selecionado ou pesquise
        as políticas fictícias disponíveis.
        Cada consulta é independente, sem memória das perguntas anteriores.
      </p>
      <form className="copilot-form" onSubmit={handleSubmit}>
        <label htmlFor="copilot-period">Período da consulta</label>
        <input
          id="copilot-period"
          type="month"
          min="2000-01"
          max="2100-12"
          required
          disabled={busy}
          value={period}
          onChange={(event) => setPeriod(event.target.value)}
        />

        <label htmlFor="copilot-question">Sua pergunta</label>
        <textarea
          id="copilot-question"
          required
          maxLength={2000}
          rows={4}
          disabled={busy}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ex.: Quanto do orçamento foi utilizado neste período?"
        />

        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? 'Consultando os dados...' : 'Perguntar ao copiloto'}
        </button>
      </form>

      {busy && (
        <p role="status">
          Consultando os dados e preparando a resposta.
        </p>
      )}

      {error && <p className="error-message" role="alert">{error}</p>}

      {answer && (
        <div className="copilot-answer">
          <p className="eyebrow">
            {answer.response.mode === 'mock'
              ? 'MODO DEMONSTRAÇÃO — SEM IA'
              : 'RESPOSTA GERADA COM GEMINI'}
          </p>

          <h3>Consulta de {answer.period.split('-').reverse().join('/')}</h3>
          <p><strong>Pergunta:</strong> {answer.question}</p>
          <div className="answer-text">{answer.response.answer}</div>

          <details>
            <summary>Conferir os dados utilizados</summary>

            {answer.response.tools_used.map((execution, index) => (
              <div key={`${execution.name}-${index}`}>

              <p>
                {execution.name === 'search_financial_policies'
                  ? 'Fonte: políticas fictícias carregadas. A seleção por vigência ainda não é aplicada.'
                  : `Fonte: dados financeiros de ${String(execution.arguments.month).padStart(2, '0')}/${execution.arguments.year}.`}
              </p>

              {execution.name === 'review_budget_policy' && (
                <p>
                  Esta análise também utiliza políticas fictícias.
                  A vigência dos documentos para o período selecionado
                  ainda não é verificada.
                </p>
              )}

              {execution.result && (
                <dl className="source-data">
                  <div>
                    <dt>Previsto (BRL)</dt>
                    <dd>{execution.result.planned}</dd>
                  </div>
                  <div>
                    <dt>Realizado (BRL)</dt>
                    <dd>{execution.result.actual}</dd>
                  </div>
                  <div>
                    <dt>Saldo (BRL)</dt>
                    <dd>{execution.result.balance}</dd>
                  </div>
                  <div>
                    <dt>Utilização</dt>
                    <dd>
                      {execution.result.utilization_percentage === null
                        ? 'Não se aplica'
                        : `${execution.result.utilization_percentage}%`}
                    </dd>
                  </div>
                </dl>
                  )}


                <p>
                  Consulta realizada:{' '}
                  {execution.name === 'review_budget_policy'
                    ? 'Análise financeira com políticas'
                    : execution.name === 'search_financial_policies'
                      ? 'Busca de políticas'
                      : execution.name === 'get_financial_alerts'
                        ? 'Alertas financeiros'
                        : execution.name === 'compare_categories'
                          ? 'Comparação por categoria'
                          : 'Resumo geral'}
                </p>

                {(
                  execution.name === 'search_financial_policies' ||
                  execution.name === 'review_budget_policy'
                ) && (
                  
                  <div>
                    <h4>Trechos recuperados</h4>

                    <p>
                      Os candidatos abaixo foram encontrados pela busca.
                      As fontes citadas estão identificadas.
                    </p>

                    {execution.sources.map((source) => (
                      <details key={source.source_id}>
                        <summary>
                          [{source.source_id}] {source.document_id}
                          {' '}— {source.section_id}
                          {execution.cited_source_ids.includes(source.source_id)
                            ? ' — Citada na resposta'
                            : ' — Candidata recuperada'}
                        </summary>

                        <p>
                          Versão {source.version}
                          {' '}— {source.section_title}
                        </p>

                        <p style={{ whiteSpace: 'pre-wrap' }}>
                          {source.text}
                        </p>

                        <p>
                          Similaridade: {source.similarity.toFixed(4)}.
                          Esse valor não representa uma probabilidade de acerto.
                        </p>
                      </details>
                    ))}
                  </div>
                )}
                

                {(
                  execution.name === 'get_financial_alerts' ||
                  execution.name === 'review_budget_policy'
                ) && (
                  <>
                    <p>
                      {execution.alerts.length} alerta(s) encontrado(s).
                    </p>

                    {execution.alerts.length === 0 ? (
                      <p>
                        Nenhuma categoria atingiu as regras atuais de alerta.
                      </p>
                    ) : (
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>Categoria</th>
                              <th>Nível</th>
                              <th>Alerta</th>
                              <th>Previsto (R$)</th>
                              <th>Realizado (R$)</th>
                              <th>Saldo (R$)</th>
                            </tr>
                          </thead>

                          <tbody>
                            {execution.alerts.map((alert) => (
                              <tr key={alert.category_id}>
                                <td>{alert.category_name}</td>
                                <td>
                                  {alert.severity === 'critical'
                                    ? 'Crítico'
                                    : 'Atenção'}
                                </td>
                                <td>{alert.message}</td>
                                <td>{alert.planned.replace('.', ',')}</td>
                                <td>{alert.actual.replace('.', ',')}</td>
                                <td>{alert.balance.replace('.', ',')}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </>
                )}

                {execution.categories && execution.categories.length > 0 && (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Categoria</th>
                          <th>Previsto (R$)</th>
                          <th>Realizado (R$)</th>
                          <th>Saldo (R$)</th>
                          <th>Utilização</th>
                        </tr>
                      </thead>
                      <tbody>
                        {execution.categories.map((category) => (
                          <tr key={category.category_id}>
                            <td>{category.category_name}</td>
                            <td>{category.summary.planned.replace('.', ',')}</td>
                            <td>{category.summary.actual.replace('.', ',')}</td>
                            <td>{category.summary.balance.replace('.', ',')}</td>
                            <td>
                              {category.summary.utilization_percentage === null
                                ? 'Não se aplica'
                                : `${category.summary.utilization_percentage.replace('.', ',')}%`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {execution.name === 'compare_categories' &&
                  execution.categories?.length === 0 && (
                    <p>Não há orçamento ou despesas por categoria neste período.</p>
                  )}
              </div>
            ))}
          </details>

          <p className="copilot-note">
            Confira a explicação com os dados utilizados.
            O texto gerado pode conter erros.
          </p>
        </div>
      )}
    </section>
  )
}