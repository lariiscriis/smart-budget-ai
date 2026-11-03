import { useState } from 'react'
import type { FormEvent } from 'react'

import {
  confirmImport,
  getImport,
  listImports,
  previewImport,
} from '../services/imports'
import type {
  ImportBatch,
  ImportHistoryItem,
} from '../services/imports'

export default function ImportPanel() {
  const [file, setFile] = useState<File | null>(null)
  const [batch, setBatch] = useState<ImportBatch | null>(null)
  const [history, setHistory] = useState<ImportHistoryItem[]>([])
  const [acceptPartial, setAcceptPartial] = useState(false)
  const [needsStatus, setNeedsStatus] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function run(action: () => Promise<void>) {
    if (busy) return

    setBusy(true)
    setError(null)
    setMessage(null)

    try {
      await action()
    } catch (error: unknown) {
      setError(
        error instanceof Error ? error.message : 'Erro inesperado.',
      )
    } finally {
      setBusy(false)
    }
  }

  function selectBatch(next: ImportBatch) {
    setBatch(next)
    setAcceptPartial(false)
    setNeedsStatus(false)
  }

  function handlePreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    void run(async () => {
      if (!file) throw new Error('Selecione uma planilha.')

      if (file.size > 2 * 1024 * 1024) {
        throw new Error('O arquivo deve ter até 2 MB.')
      }

      const result = await previewImport(file)
      selectBatch(result)
    })
  }

  function handleConfirm() {
    if (!batch) return

    void run(async () => {
      setNeedsStatus(true)

      await confirmImport(batch.import_id, acceptPartial)
      const updated = await getImport(batch.import_id)

      selectBatch(updated)
      setMessage(
        `Importação concluída: ${updated.saved_count} despesa(s) gravada(s). Consulte novamente o dashboard.`,
      )
    })
  }

  const hasRejectedRows = batch
    ? batch.report.invalid_count > 0 || batch.report.duplicate_count > 0
    : false

  return (
    <section className="import-panel" aria-labelledby="import-heading">
      <h2 id="import-heading">Importar despesas</h2>
      <p>
        Envie CSV ou XLSX, revise os registros e confirme a gravação.
        Limite: 2 MB e 1.000 registros.
      </p>
      <p>
        Colunas: categoria_id, descricao, data e valor.
        No XLSX, utilizamos a primeira aba.
      </p>

      <form className="period-form" onSubmit={handlePreview}>
        <div>
          <label htmlFor="expense-file">Planilha de despesas</label>
          <input
            id="expense-file"
            type="file"
            accept=".csv,.xlsx"
            required
            disabled={busy}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null)
              setBatch(null)
              setAcceptPartial(false)
              setNeedsStatus(false)
              setError(null)
              setMessage(null)
            }}
          />
        </div>

        <button type="submit" disabled={busy || !file}>
          Analisar planilha
        </button>
      </form>

      {busy && <p role="status">Processando solicitação...</p>}
      {error && <p className="error-message" role="alert">{error}</p>}
      {message && <p className="success-message" role="status">{message}</p>}

      {batch && (
        <div className="import-review">
          <h3>{batch.filename}</h3>
          <p>
            Status: {batch.status === 'completed' ? 'Concluída' : 'Aguardando confirmação'}
          </p>

          <dl className="import-counts">
            <div><dt>Total</dt><dd>{batch.report.total_rows}</dd></div>
            <div><dt>Válidos</dt><dd>{batch.report.valid_count}</dd></div>
            <div><dt>Inválidos</dt><dd>{batch.report.invalid_count}</dd></div>
            <div><dt>Duplicados</dt><dd>{batch.report.duplicate_count}</dd></div>
          </dl>

          <details>
            <summary>Revisar registros válidos</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Posição</th>
                    <th>Categoria ID</th>
                    <th>Descrição</th>
                    <th>Data</th>
                    <th>Valor (R$)</th>
                  </tr>
                </thead>
                <tbody>
                  {batch.report.valid_rows.map((item) => (
                    <tr key={item.row}>
                      <td>{item.row}</td>
                      <td>{item.data.category_id}</td>
                      <td>{item.data.description}</td>
                      <td>{item.data.expense_date}</td>
                      <td>{item.data.amount.replace('.', ',')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          <details>
            <summary>Revisar erros e possíveis duplicatas</summary>
            <ul>
              {batch.report.errors.map((item) => (
                <li key={`error-${item.row}`}>
                  Posição {item.row}: {item.messages.join('; ')}
                </li>
              ))}
              {batch.report.duplicates.map((item) => (
                <li key={`duplicate-${item.row}`}>
                  Posição {item.row}: igual à posição {item.same_as_row}.
                </li>
              ))}
            </ul>
          </details>

          {batch.status === 'completed' ? (
            <p className="success-message">
              {batch.saved_count} despesa(s) gravada(s). Este arquivo já foi processado.
            </p>
          ) : (
            <>
              {hasRejectedRows && (
                <label className="partial-confirmation">
                  <input
                    type="checkbox"
                    checked={acceptPartial}
                    disabled={busy}
                    onChange={(event) => setAcceptPartial(event.target.checked)}
                  />
                  Revisei o relatório e autorizo salvar apenas os válidos,
                  excluindo os inválidos e duplicados.
                </label>
              )}

              <button
                className="primary-button"
                type="button"
                disabled={
                  busy ||
                  needsStatus ||
                  batch.report.valid_count === 0 ||
                  (hasRejectedRows && !acceptPartial)
                }
                onClick={handleConfirm}
              >
                Confirmar gravação de {batch.report.valid_count} despesa(s)
              </button>
            </>
          )}

          {needsStatus && (
            <p role="status">
              A confirmação pode ter sido processada. Consulte o status antes de repetir.
            </p>
          )}

          <button
            className="secondary-button"
            type="button"
            disabled={busy}
            onClick={() => void run(async () => {
              selectBatch(await getImport(batch.import_id))
            })}
          >
            Consultar status
          </button>
        </div>
      )}

      <div className="import-history">
        <h3>Últimas 20 importações</h3>
        <button
          className="secondary-button"
          type="button"
          disabled={busy}
          onClick={() => void run(async () => {
            const result = await listImports()
            setHistory(result)
            if (result.length === 0) {
              setMessage('Nenhuma importação registrada.')
            }
          })}
        >
          Consultar / atualizar histórico
        </button>

        <ul className="category-list">
          {history.map((item) => (
            <li key={item.import_id}>
              <strong>{item.filename}</strong>
              <span>
                {item.status === 'completed' ? 'Concluída' : 'Pendente'}
                {' · '}{item.saved_count} gravada(s)
              </span>
              <button
                className="secondary-button"
                type="button"
                disabled={busy}
                onClick={() => void run(async () => {
                  selectBatch(await getImport(item.import_id))
                })}
              >
                Abrir relatório
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}