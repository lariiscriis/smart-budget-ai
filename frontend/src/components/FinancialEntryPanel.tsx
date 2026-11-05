import { useState } from 'react'
import type { FormEvent } from 'react'

import { listCategories } from '../services/categories'
import type { Category } from '../services/categories'
import { createBudget, createExpense } from '../services/entries'

type EntryKind = 'budget' | 'expense'

function todayLocal() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')

  return `${now.getFullYear()}-${month}-${day}`
}

function normalizeAmount(value: string): string {
  const normalized = value.trim().replace(',', '.')

  if (!/^\d{1,12}(\.\d{1,2})?$/.test(normalized)) {
    throw new Error(
      'Use até 12 dígitos inteiros e duas casas decimais, sem separador de milhares. Ex.: 1500,50.',
    )
  }

  const [integer, fraction = ''] = normalized.split('.')

  return `${integer}.${fraction.padEnd(2, '0')}`
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Erro inesperado.'
}

export default function FinancialEntryPanel() {
  const [kind, setKind] = useState<EntryKind>('budget')
  const [categories, setCategories] = useState<Category[]>([])
  const [categoryId, setCategoryId] = useState('')
  const [period, setPeriod] = useState(() => todayLocal().slice(0, 7))
  const [expenseDate, setExpenseDate] = useState(todayLocal)
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
      const all: Category[] = []
      const pageSize = 100
      let offset = 0

      while (true) {
        const page = await listCategories(offset, pageSize, 'expense')
        all.push(...page)

        if (page.length < pageSize) break
        offset += pageSize
      }

      setCategories(all)
      setCategoryId('')

      if (all.length === 0) {
        setError('Cadastre uma categoria no painel abaixo antes de lançar valores.')
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
      normalizedAmount = normalizeAmount(amount)

      if (
        kind === 'expense' &&
        /^0+\.00$/.test(normalizedAmount)
      ) {
        throw new Error('A despesa precisa ter valor maior que zero.')
      }

      if (kind === 'expense' && !description.trim()) {
        throw new Error('Preencha a descrição da despesa.')
      }

      if (!categories.some((category) => String(category.id) === categoryId)) {
        throw new Error('Selecione uma categoria válida.')
      }
    } catch (error: unknown) {
      setError(getErrorMessage(error))
      return
    }

    setBusy(true)

    try {
      if (kind === 'budget') {
        const [year, month] = period.split('-').map(Number)

        await createBudget({
          category_id: Number(categoryId),
          year,
          month,
          amount: normalizedAmount,
        })
      } else {
        await createExpense({
          category_id: Number(categoryId),
          description: description.trim(),
          expense_date: expenseDate,
          amount: normalizedAmount,
        })
      }

      setAmount('')
      setDescription('')
      setSuccess(
        `${kind === 'budget' ? 'Orçamento' : 'Despesa'} cadastrado com sucesso. Consulte novamente o período no dashboard para atualizar os indicadores.`,
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
      <p>Registre o valor previsto ou uma despesa realizada.</p>

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
                  setKind(event.target.value as EntryKind)
                  setError(null)
                  setSuccess(null)
                  setAmount('')
                }}
              >
                <option value="budget">Orçamento previsto</option>
                <option value="expense">Despesa realizada</option>
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
                  Data da despesa
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
