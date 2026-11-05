import { useEffect, useState } from 'react'
import { isRecord, requestRecord } from '../services/recordsApi'

type Audit = { id: number; actor: { email: string }; actor_kind: string; action: string; entity: string; entity_id: string; occurred_at: string; changes: Record<string, unknown> }
const actions: Record<string, string> = { create: 'Criação', update: 'Atualização', delete: 'Exclusão', migrate: 'Migração' }

export default function AuditPanel() {
  const [rows, setRows] = useState<Audit[]>([])
  const [offset, setOffset] = useState(0)
  const [reload, setReload] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await requestRecord(`/audit?offset=${offset}&limit=20`)
        if (!Array.isArray(data) || !data.every((item) => isRecord(item) && typeof item.id === 'number' &&
          isRecord(item.actor) && typeof item.actor.email === 'string' && typeof item.actor_kind === 'string' &&
          typeof item.action === 'string' && typeof item.entity === 'string' && typeof item.entity_id === 'string' &&
          typeof item.occurred_at === 'string' && Number.isFinite(Date.parse(item.occurred_at)) && isRecord(item.changes))) {
          throw new Error('A API retornou um histórico em formato inesperado.')
        }
        if (active) setRows(data as Audit[])
      } catch (err: unknown) { if (active) setError(err instanceof Error ? err.message : 'Não foi possível carregar o histórico.') }
      finally { if (active) setLoading(false) }
    }
    void load()
    return () => { active = false }
  }, [offset, reload])
  return <section aria-labelledby="audit-heading">
    <h2 id="audit-heading">Histórico do espaço de trabalho</h2>
    <p>Criações, alterações, exclusões e migração de dados da base compartilhada. A auditoria é somente leitura.</p>
    <button className="secondary-button" type="button" disabled={loading} onClick={() => setReload((value) => value + 1)}>Atualizar histórico</button>
    {loading && <p role="status">Consultando auditoria...</p>}
    {error && <p className="error-message" role="alert">{error}</p>}
    {!loading && !error && <div className="table-scroll"><table><caption>Página {offset / 20 + 1}</caption>
      <thead><tr><th>Data</th><th>Usuário</th><th>Ação</th><th>Registro</th><th>Mudanças</th></tr></thead>
      <tbody>{rows.map((row) => <tr key={row.id}>
        <td>{new Date(row.occurred_at).toLocaleString('pt-BR')}</td><td>{row.actor.email} · {row.actor_kind}</td>
        <td>{actions[row.action] ?? row.action}</td><td>{row.entity} #{row.entity_id}</td>
        <td><details><summary>Ver mudanças</summary><pre>{JSON.stringify(row.changes, null, 2)}</pre></details></td>
      </tr>)}</tbody>
    </table>{rows.length === 0 && <p>Nenhuma alteração nesta página.</p>}</div>}
    <div className="pagination">
      <button className="secondary-button" type="button" disabled={loading || offset === 0} onClick={() => setOffset((value) => Math.max(0, value - 20))}>Anterior</button>
      <button className="secondary-button" type="button" disabled={loading || Boolean(error) || rows.length < 20} onClick={() => setOffset((value) => value + 20)}>Próxima</button>
    </div>
  </section>
}
