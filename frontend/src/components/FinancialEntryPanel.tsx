import { useState } from 'react'
import type { FormEvent } from 'react'

import { listAllCategories } from '../services/categories'
import type { Category } from '../services/categories'
import { createBudget, createExpense } from '../services/entries'
import { createIncome } from '../services/incomes'
import { normalizeAmount, parsePeriod, todayLocal, validateDate } from '../utils/entryForm'
import CampaignSelect from './CampaignSelect'

type EntryKind = 'budget' | 'expense' | 'income'

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Erro inesperado.'
}

export default function FinancialEntryPanel({ onIncomeCreated }: { onIncomeCreated?: (date: string) => void }) {
  const [kind, setKind] = useState<EntryKind>('budget')
  const [categories, setCategories] = useState<Category[]>([])
  const [categoryId, setCategoryId] = useState('')
  const [period, setPeriod] = useState(() => todayLocal().slice(0, 7))
  const [expenseDate, setExpenseDate] = useState(todayLocal)
  const [campaignId, setCampaignId] = useState('')
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  async function loadCategories() {
    if (busy) return

    setBusy(true)
    setError(null)
    setSuccess(null)

    try {
      const all = await listAllCategories(kind === 'income' ? 'income' : 'expense')

      setCategories(all)
      setCategoryId('')

      if (all.length === 0) {
        setError(`Cadastre uma categoria do tipo ${kind === 'income' ? 'Receita' : 'Despesa'} no painel de categorias antes de lançar valores.`)
      }
    } catch (error: unknown) {
      setError(getErrorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (busy) return

    setError(null)
    setSuccess(null)

    let normalizedAmount: string

    try {
      normalizedAmount = normalizeAmount(amount, kind !== 'budget')
      if (kind === 'budget') parsePeriod(period)
      else {
        validateDate(expenseDate)
        if (!description.trim() || description.trim().length > 255) throw new Error('Preencha uma descrição válida com até 255 caracteres.')
        if (campaignId && (!Number.isSafeInteger(Number(campaignId)) || Number(campaignId) <= 0)) throw new Error('Selecione uma campanha válida ou mantenha sem campanha.')
      }
      const expectedType = kind === 'income' ? 'income' : 'expense'
      if (!categories.some((category) => String(category.id) === categoryId && category.type === expectedType)) {
        throw new Error('Selecione uma categoria válida.')
      }
    } catch (error: unknown) {
      setError(getErrorMessage(error))
      return
    }

    setBusy(true)

    try {
      if (kind === 'budget') {
        const { year, month } = parsePeriod(period)

        await createBudget({
          category_id: Number(categoryId),
          year,
          month,
          amount: normalizedAmount,
        })
      } else if (kind === 'expense') {
        await createExpense({
          category_id: Number(categoryId),
          campaign_id: campaignId ? Number(campaignId) : null,
          description: description.trim(),
          expense_date: expenseDate,
          amount: normalizedAmount,
        })
      } else {
        await createIncome({
          category_id: Number(categoryId),
          campaign_id: campaignId ? Number(campaignId) : null,
          description: description.trim(), income_date: expenseDate, amount: normalizedAmount,
        })
        onIncomeCreated?.(expenseDate)
      }

      setAmount('')
      setDescription('')
      setSuccess(
        `${kind === 'budget' ? 'Orçamento cadastrado' : kind === 'income' ? 'Receita cadastrada' : 'Despesa cadastrada'} com sucesso. Consulte novamente o período no dashboard para atualizar os indicadores.`,
      )
    } catch (error: unknown) {
      setError(
        `${getErrorMessage(error)} Se houve falha de conexão, confira os registros antes de reenviar.`,
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="entry-panel" aria-labelledby="entry-heading">
      <h2 id="entry-heading">Novo lançamento</h2>
      <p>Registre o orçamento previsto, uma despesa ou uma receita realizada.</p>

      <button
        className="secondary-button"
        type="button"
        disabled={busy}
        onClick={() => void loadCategories()}
      >
        Carregar / atualizar categorias
      </button>

      <form className="entry-form" onSubmit={handleSubmit}>
        <fieldset disabled={busy}>
          <div className="entry-fields">
            <label>
              Tipo de lançamento
              <select
                value={kind}
                onChange={(event) => {
                  const next = event.target.value as EntryKind
                  if ((next === 'income') !== (kind === 'income')) {
                    setCategories([])
                    setCategoryId('')
                  }
                  setKind(next)
                  setCampaignId('')
                  setError(null)
                  setSuccess(null)
                  setAmount('')
                }}
              >
                <option value="budget">Orçamento previsto</option>
                <option value="expense">Despesa realizada</option>
                <option value="income">Receita realizada</option>
              </select>
            </label>

            <label>
              Categoria
              <select
                required
                value={categoryId}
                onChange={(event) => setCategoryId(event.target.value)}
              >
                <option value="">Selecione uma categoria</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </label>

            {kind === 'budget' ? (
              <label>
                Mês do orçamento
                <input
                  type="month"
                  required
                  min="2000-01"
                  max="2100-12"
                  value={period}
                  onChange={(event) => setPeriod(event.target.value)}
                />
              </label>
            ) : (
              <>
                <label>
                  {kind === 'income' ? 'Data da receita' : 'Data da despesa'}
                  <input
                    type="date"
                    required
                    min="2000-01-01"
                    max="2100-12-31"
                    value={expenseDate}
                    onChange={(event) => setExpenseDate(event.target.value)}
                  />
                </label>

                <label>
                  Descrição
                  <input
                    type="text"
                    required
                    maxLength={255}
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                  />
                </label>
              </>
            )}

            <label>
              Valor em reais
              <input
                type="text"
                inputMode="decimal"
                required
                maxLength={15}
                placeholder="Ex.: 1500,50"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
              />
            </label>
          </div>

          {kind !== 'budget' && <div className="entry-fields"><CampaignSelect value={campaignId} onChange={setCampaignId} disabled={busy} /></div>}

          <button
            className="primary-button"
            type="submit"
            disabled={categories.length === 0}
          >
            {busy ? 'Processando...' : 'Salvar lançamento'}
          </button>
        </fieldset>
      </form>

      {busy && <p role="status">Processando solicitação...</p>}
      {error && <p className="error-message" role="alert">{error}</p>}
      {success && <p className="success-message" role="status">{success}</p>}
    </section>
  )
}
