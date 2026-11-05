import { useState } from 'react'
import type { FormEvent } from 'react'

import { createCategory, listCategories } from '../services/categories'
import type { Category, CategoryType } from '../services/categories'
import RecordAttribution from './RecordAttribution'

const PAGE_SIZE = 20

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Erro inesperado.'
}

export default function CategoriesPanel() {
  const [name, setName] = useState('')
  const [type, setType] = useState<CategoryType>('expense')
  const [categories, setCategories] = useState<Category[]>([])
  const [offset, setOffset] = useState(0)
  const [hasLoaded, setHasLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  async function loadPage(nextOffset: number) {
    if (busy) return

    setBusy(true)
    setError(null)
    setSuccess(null)

    try {
      const result = await listCategories(nextOffset, PAGE_SIZE)
      setCategories(result)
      setOffset(nextOffset)
      setHasLoaded(true)
    } catch (error: unknown) {
      setError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (busy) return

    const cleanedName = name.trim()

    if (!cleanedName) {
      setError('O nome não pode conter apenas espaços.')
      setSuccess(null)
      return
    }

    setBusy(true)
    setError(null)
    setSuccess(null)

    try {
      const created = await createCategory(cleanedName, type)

      setName('')
      setSuccess(`Categoria "${created.name}" cadastrada. Atualize a lista para consultar.`)
    } catch (error: unknown) {
      setError(
        `${errorMessage(error)} Se houve falha de conexão, consulte a lista antes de repetir o cadastro.`,
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="categories-panel" aria-labelledby="categories-heading">
      <h2 id="categories-heading">Categorias</h2>
      <p>Organize os grupos utilizados nos orçamentos e nas despesas.</p>

      <form className="period-form" onSubmit={handleCreate}>
        <div>
          <label htmlFor="category-name">Nome da categoria</label>
          <input
            id="category-name"
            type="text"
            required
            maxLength={100}
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={busy}
            placeholder="Ex.: Tecnologia"
          />
        </div>

        <label htmlFor="category-type">Tipo</label>
        <select
          id="category-type"
          value={type}
          disabled={busy}
          onChange={(event) => setType(event.target.value as CategoryType)}
        >
          <option value="expense">Despesa</option>
          <option value="income">Receita</option>
        </select>

        <button type="submit" disabled={busy}>
          Cadastrar categoria
        </button>
      </form>

      {success && <p className="success-message" role="status">{success}</p>}
      {error && <p className="error-message" role="alert">{error}</p>}
      {busy && <p role="status">Processando...</p>}

      <button
        className="secondary-button"
        type="button"
        onClick={() => void loadPage(0)}
        disabled={busy}
      >
        {hasLoaded ? 'Atualizar lista' : 'Carregar categorias'}
      </button>

      {hasLoaded && (
        <>
          <p>Página {offset / PAGE_SIZE + 1}</p>

          {categories.length === 0 ? (
            <p>Nenhuma categoria nesta página.</p>
          ) : (
            <ul className="category-list">
              {categories.map((category) => (
                <li key={category.id}>
                  <span>{category.name} · {category.type === 'income' ? 'Receita' : 'Despesa'}</span>
                  <small>ID: {category.id}</small>
                  <RecordAttribution record={category} />
                </li>
              ))}
            </ul>
          )}

          <div className="pagination">
            <button
              className="secondary-button"
              type="button"
              disabled={busy || offset === 0}
              onClick={() => void loadPage(offset - PAGE_SIZE)}
            >
              Anterior
            </button>

            <button
              className="secondary-button"
              type="button"
              disabled={busy || categories.length < PAGE_SIZE}
              onClick={() => void loadPage(offset + PAGE_SIZE)}
            >
              Próxima
            </button>
          </div>
        </>
      )}
    </section>
  )
}
