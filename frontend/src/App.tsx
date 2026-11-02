import { useState } from 'react'

function App() {
  const [message, setMessage] = useState('Conexão ainda não testada.')
  const [isLoading, setIsLoading] = useState(false)

  async function checkConnection() {
    setIsLoading(true)
    setMessage('Consultando a API...')

    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL

      if (!apiBaseUrl) {
        throw new Error('A variável VITE_API_BASE_URL não foi configurada.')
      }

      const response = await fetch(`${apiBaseUrl}/health`)

      if (!response.ok) {
        throw new Error(`A API retornou HTTP ${response.status}.`)
      }

      const data: unknown = await response.json()

      if (
        typeof data !== 'object' ||
        data === null ||
        !('status' in data) ||
        data.status !== 'ok'
      ) {
        throw new Error('A API retornou uma resposta inesperada.')
      }

      setMessage('Conexão com a API funcionando! Status: ok.')
    } catch (error: unknown) {
      const detail =
        error instanceof Error ? error.message : 'Erro desconhecido.'

      setMessage(`Não foi possível confirmar a conexão. ${detail}`)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main>
      <h1>Smart Budget AI</h1>
      <p>Teste de comunicação entre React e FastAPI.</p>

      <button
        type="button"
        onClick={checkConnection}
        disabled={isLoading}
      >
        {isLoading ? 'Testando...' : 'Testar conexão'}
      </button>

      <p role="status">{message}</p>
    </main>
  )
}

export default App