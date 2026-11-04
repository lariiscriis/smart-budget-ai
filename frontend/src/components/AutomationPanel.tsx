import { useEffect, useState } from 'react'

import {
  getAlerts,
  getAutomationJobs,
  retryAutomationJob,
} from '../services/automation'

import type {
  AlertsResponse,
  AutomationJob,
} from '../services/automation'

type Props = {
  year: number
  month: number
}

const statusLabels: Record<AutomationJob['status'], string> = {
  pending: 'Na fila',
  running: 'Em execução',
  succeeded: 'Concluída',
  failed: 'Falhou',
}

const money = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

function formatMoney(value: string): string {
  return money.format(Number(value))
}

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : 'Não foi possível concluir a operação.'
}

export default function AutomationPanel({ year, month }: Props) {
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null)
  const [alertsLoading, setAlertsLoading] = useState(true)
  const [alertsError, setAlertsError] = useState<string | null>(null)

  const [jobs, setJobs] = useState<AutomationJob[]>([])
  const [jobsLoading, setJobsLoading] = useState(true)
  const [jobsError, setJobsError] = useState<string | null>(null)

  const [retryingId, setRetryingId] = useState<number | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let ignore = false

    async function loadAlerts() {
      setAlertsLoading(true)
      setAlertsError(null)
      setAlerts(null)

      try {
        const data = await getAlerts(year, month)

        if (!ignore) {
          setAlerts(data)
        }
      } catch (error) {
        if (!ignore) {
          setAlertsError(errorMessage(error))
        }
      } finally {
        if (!ignore) {
          setAlertsLoading(false)
        }
      }
    }

    void loadAlerts()

    return () => {
      ignore = true
    }
  }, [year, month, reload])

  useEffect(() => {
    let ignore = false

    async function loadJobs() {
      setJobsLoading(true)
      setJobsError(null)

      try {
        const data = await getAutomationJobs()

        if (!ignore) {
          setJobs(data)
        }
      } catch (error) {
        if (!ignore) {
          setJobsError(errorMessage(error))
        }
      } finally {
        if (!ignore) {
          setJobsLoading(false)
        }
      }
    }

    void loadJobs()

    return () => {
      ignore = true
    }
  }, [reload])

  async function handleRetry(jobId: number) {
    setRetryingId(jobId)
    setJobsError(null)
    setNotice(null)

    try {
      const updated = await retryAutomationJob(jobId)

      setJobs((current) =>
        current.map((job) => (job.id === updated.id ? updated : job)),
      )

      setNotice(
        `Tarefa ${jobId} recolocada na fila. Execute o processador para iniciá-la.`,
      )
    } catch (error) {
      setJobsError(errorMessage(error))
    } finally {
      setRetryingId(null)
    }
  }

  return (
    <section aria-label="Alertas e automações">
      <header>
        <h2>Alertas e automações</h2>

        <button
          type="button"
          disabled={
            alertsLoading || jobsLoading || retryingId !== null
          }
          onClick={() => setReload((current) => current + 1)}
        >
          Atualizar dados
        </button>
      </header>

      <section aria-labelledby="financial-alerts-title">
        <h3 id="financial-alerts-title">
          Alertas de {String(month).padStart(2, '0')}/{year}
        </h3>

        {alertsLoading && (
          <p role="status">Carregando alertas...</p>
        )}

        {alertsError && <p role="alert">{alertsError}</p>}

        {!alertsLoading && !alertsError && alerts && (
          <>
            <p>
              {alerts.count} alerta(s) encontrado(s).
              {' '}Versão das regras: {alerts.rules_version}.
            </p>

            {alerts.count === 0 ? (
              <p>
                Nenhuma categoria atingiu as regras de alerta
                neste período.
              </p>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Categoria</th>
                      <th>Nível</th>
                      <th>Alerta</th>
                      <th>Previsto</th>
                      <th>Realizado</th>
                      <th>Saldo</th>
                    </tr>
                  </thead>

                  <tbody>
                    {alerts.alerts.map((alert) => (
                      <tr key={alert.category_id}>
                        <td>{alert.category_name}</td>
                        <td>
                          {alert.severity === 'critical'
                            ? 'Crítico'
                            : 'Atenção'}
                        </td>
                        <td>{alert.message}</td>
                        <td>{formatMoney(alert.planned)}</td>
                        <td>{formatMoney(alert.actual)}</td>
                        <td>{formatMoney(alert.balance)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      <section aria-labelledby="automation-history-title">
        <h3 id="automation-history-title">
          Histórico de automações
        </h3>

        <p>
          Até 20 tarefas mais recentes, incluindo todos os períodos.
        </p>

        {notice && <p role="status">{notice}</p>}
        {jobsError && <p role="alert">{jobsError}</p>}

        {jobsLoading ? (
          <p role="status">Carregando histórico...</p>
        ) : jobsError ? (
          <p>Atualize os dados para consultar o estado atual.</p>
        ) : jobs.length === 0 ? (
          <p>Nenhuma tarefa registrada.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Tarefa</th>
                  <th>Período</th>
                  <th>Status</th>
                  <th>Tentativas</th>
                  <th>Detalhes</th>
                  <th>Ação</th>
                </tr>
              </thead>

              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>#{job.id}</td>
                    <td>
                      {String(job.month).padStart(2, '0')}/{job.year}
                    </td>
                    <td>{statusLabels[job.status]}</td>
                    <td>{job.attempts}</td>
                    <td>
                      <details>
                        <summary>Ver detalhes</summary>

                        <p>Importação: {job.import_id}</p>

                        {job.last_error && (
                          <p>Erro registrado: {job.last_error}</p>
                        )}

                        {job.result !== null && (
                          <pre>
                            {JSON.stringify(job.result, null, 2)}
                          </pre>
                        )}
                      </details>
                    </td>
                    <td>
                      {job.status === 'failed' ? (
                        <button
                          type="button"
                          disabled={retryingId !== null}
                          onClick={() => void handleRetry(job.id)}
                        >
                          {retryingId === job.id
                            ? 'Recolocando...'
                            : 'Recolocar na fila'}
                        </button>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  )
}