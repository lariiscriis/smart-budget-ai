import type { AttributedRecord } from '../services/attribution'

const time = (value: string) => Number.isFinite(Date.parse(value))
  ? new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : 'data indisponível'

export default function RecordAttribution({ record }: { record: AttributedRecord }) {
  if (!record.created_by_user) return null
  if (record.attribution_source === 'legacy_owner') return <small>Responsável legado: {record.created_by_user.email} · atribuição migrada
    {record.updated_by_user && record.updated_at && ` · Última alteração atribuída: ${record.updated_by_user.email}, ${time(record.updated_at)}`}
  </small>
  return <small>
    Criado por {record.created_by_user.email}{record.created_at && ` · ${time(record.created_at)}`}
    {record.updated_by_user && record.updated_at && record.updated_at !== record.created_at &&
      ` · Última alteração: ${record.updated_by_user.email}, ${time(record.updated_at)}`}
  </small>
}
