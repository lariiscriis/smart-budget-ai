# Aurora — frontend

## Acesso

O endereço inicial abre a landing page da Aurora. **Entrar no sistema** abre
`/#login`, com o formulário de acesso existente e a opção **Criar uma conta**.
Com uma sessão válida, a landing oferece **Ir para a aplicação** (`/#app`),
sem exigir outro login. Acesso direto a `/#app` continua protegido pela
verificação da sessão. **Voltar ao início** retorna à landing (`/#inicio`).
Os caminhos usam fragmentos de URL e não exigem novas regras no servidor.

Para conferir a navegação, abra `http://localhost:5173` sem sessão, siga para
login, alterne para cadastro e volte ao início. Após entrar, use as abas do
sistema; abra `/#inicio` para verificar o acesso direto à aplicação. Recarregue
`/#app` e confirme a restauração da sessão. Após **Sair**, `/#app` deve mostrar
o login. Confira também a página inicial em desktop (por exemplo, 1366 × 768)
e em celular: no desktop ela ocupa a altura da janela; no celular o conteúdo
se reorganiza em uma coluna e pode rolar para manter a leitura acessível.

Ao abrir a aplicação, a sessão é verificada antes de renderizar qualquer tela
financeira. Use **Criar uma conta** para cadastrar email e senha (8–128
caracteres), ou **Entrar**. No demo, cadastro novo entra no espaço Aurora e
compartilha os registros existentes com os demais membros. Use somente dados
fictícios. Departamentos reais exigem provisionamento administrativo, sem esse
autocadastro; veja o README do backend. **Sair** revoga a sessão no servidor e desmonta
as telas e seus estados. Uma resposta 401 exige novo login.

A credencial fica exclusivamente em cookie HttpOnly, com expiração validada no
backend. O token CSRF fica apenas em memória e é restaurado via `/auth/me` após
recarregar a página. Todos os serviços enviam cookies e a proteção CSRF nas
escritas, inclusive upload e confirmação de importação. Não há tokens em
localStorage, sessionStorage ou URLs. Voltar à aba verifica novamente a sessão
e a associação ao espaço. A troca de usuário/espaço limpa os estados financeiros.

O cabeçalho identifica o espaço atual e a base compartilhada. Categorias,
campanhas e receitas mostram criador/último editor; registros migrados aparecem
como “Responsável legado”, sem afirmar autoria histórica desconhecida. A aba
**Auditoria** lista criações, alterações, exclusões e migração, com usuário,
origem da ação e mudanças relevantes. Seu conteúdo é somente leitura e restrito
ao espaço autenticado. Os gráficos incluem os registros de todos os membros.

Para conferir, crie duas contas no demo, lance uma despesa na primeira e entre
com a segunda: após consultar o mesmo mês, ambas veem a despesa e o mesmo total.
O campo de autoria e a auditoria continuam identificando quem fez o lançamento.

No desenvolvimento, `/api` é encaminhado pelo Vite para `http://127.0.0.1:8000`.
Inicie o backend com `$env:AUTH_COOKIE_SECURE="false"` apenas para HTTP local.
Abra `http://localhost:5173`; não é necessário alterar `.env`. Em produção,
use HTTPS com cookie Secure e proxy `/api` no mesmo site; para o build use
`$env:VITE_API_BASE_URL="/api"` no processo. Não exponha valores de configuração
ou tokens em logs.

Na aba **Registros**:

- Em **Novo lançamento**, selecione **Receita realizada** e clique em
  **Carregar / atualizar categorias**. Só aparecem categorias `income`.
  Preencha data, descrição e valor positivo com até duas casas decimais.
- Em receitas e despesas, **Campanha (opcional)** permite manter **Sem campanha**
  ou carregar todas as campanhas e selecionar uma. Orçamentos não recebem campanha.
- **Receitas cadastradas** lista os registros por mês e em páginas de 20 itens.
  Após cadastrar uma receita, a lista abre o mês do lançamento e é atualizada.
  Use **Consultar / atualizar receitas** para consultar novamente, inclusive
  quando uma resposta de cadastro ficar incerta por falha de conexão.
- Em **Campanhas**, cadastre um nome de até 100 caracteres. A lista paginada é
  atualizada após o cadastro. Para usar uma campanha nova em um lançamento,
  clique em **Carregar / atualizar campanhas** no formulário.
- Cadastre categorias com tipo **Receita** ou **Despesa** no painel de categorias.

As telas usam somente as rotas existentes (`/incomes`, `/campaigns`, `/categories`,
`/expenses`, `/budgets`). Valores são enviados como strings decimais. Não há
reenvio automático de cadastros após falhas. Os estilos e cálculos dos gráficos
permanecem os mesmos; o dashboard é atualizado ao voltar para **Visão geral**.

Para iniciar, execute `npm run dev` com o backend disponível. Para verificar:
`npm test`, `npm run build` e `npm run lint`. Os testes usam dependências já
instaladas e não fazem requisições externas nem leem arquivos `.env`.

## Configuração React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```

You can also install [eslint-plugin-react-x](https://npmx.dev/package/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://npmx.dev/package/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```
