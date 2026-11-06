# Análises consultivas do copiloto Aurora

Todas as políticas e dados desta demonstração são fictícios.
Nenhum layout, autenticação, landing page ou fluxo n8n é alterado por estas análises.

## Consultas e limites

| Capacidade | Ferramenta exposta ao modelo | Consultas reutilizadas | Evidência e limites |
|---|---|---|---|
| Verificar despesa existente | `review_expense_policy(year, month, expense_id?)` | Consulta ORM tipada do lançamento e categoria; RAG existente com contexto do registro real | ID, data, valor, categoria, descrição e campanha; descrição não valida comprovante, autorização ou finalidade. Sem ID, pedir identificação. Não declara conformidade nem aprova reembolso. |
| Explicar alertas | `review_budget_policy(year, month, focus="alerts")` | `get_category_comparison`, `build_alerts`, recuperação documental | Mantém códigos, severidades e valores do backend; vincula near_limit a ORC-02, over_budget a ORC-03 e unbudgeted a ORC-04 somente se recuperadas. Ausência de seção é explícita. |
| Comparar campanha | `compare_campaign_policy(year, month, campaign_id?, campaign_name?)` | Identificação por ID/nome exato e `get_dashboard_analytics(months=1)` | Totais e quantidades de receitas/despesas vinculadas, diferença entre registros; sem orçamento próprio no modelo atual, informa que não há limite definido. Não usa orçamento de categoria, não demonstra causalidade ou lucro. |
| Preparar decisão | `review_budget_policy(year, month, focus="decision")` | Comparação, alertas, analytics de receitas/despesas/campanhas e RAG | Fatos, fontes, dúvidas, riscos e opções como sugestões. Sem escrita, aprovação, alteração orçamentária ou automação. |

A busca `search_financial_policies` continua disponível para perguntas somente
documentais; `get_financial_alerts` continua disponível para listar alertas sem
análise documental. O foco padrão `budget` preserva a análise combinada anterior.

O modelo seleciona exatamente uma ferramenta tipada e o período deve coincidir
com o selecionado. IDs e nomes devem vir da pergunta. Nenhuma ferramenta aceita
SQL, workspace escolhido pelo modelo, limite monetário, aprovação ou ação de escrita.
O contexto autenticado e a política de isolamento da sessão limitam as consultas.

As quatro análises novas são formatadas pelo backend a partir de evidências e
fontes, sem uma segunda geração livre de narrativa pelo modelo. Campos textuais
e trechos recuperados aparecem como conteúdo de referência, nunca como comandos.
A busca semântica é complementada por seções documentais necessárias à análise
que realmente existam no corpus; não são criadas fontes para seções ausentes.
O índice ausente/desatualizado continua sendo erro de configuração; corpus sem
documentos resulta em ausência explícita de suporte documental.

## Teste manual

1. No backend configurado, executar `python -m app.index_policies` para atualizar
   os embeddings após as alterações de políticas. Esse comando administrativo
   pode gravar o índice; o chat somente consulta o índice existente.
2. Usar `AI_MODE=gemini`, reiniciar o backend e entrar normalmente no aplicativo.
   O modo mock não executa a recuperação semântica e avisa essa limitação.
3. Selecionar o mês dos dados fictícios cadastrados e testar:
   - “Verifique a despesa ID 17 contra as políticas.” Substituir 17 por um ID real.
   - “Explique os alertas do mês com as políticas internas.”
   - “Compare a campanha Natal com as políticas e o limite cadastrado.” Usar nome exato real.
   - “Prepare um resumo para decisão com números, políticas, dúvidas, riscos e opções.”
4. Conferir `tools_used` na resposta de `POST /copilot/chat`: argumentos,
   evidências, números, alertas, fontes e IDs citados devem corresponder às consultas.
   A chamada usa o cookie e o token CSRF da sessão existente.
5. Repetir com ID inexistente, outro mês, registro de outro espaço, campanha
   sem movimento, ausência de política e textos de indução. A matriz detalhada
   está em `knowledge/rag-evaluation.md`, casos R09–R22.

Não concluir conformidade definitiva, aprovação de reembolso, causa de desvio,
causalidade da receita, lucro ou limite de campanha inexistente. A vigência
histórica das políticas pelo mês selecionado continua sem validação automática.

## Verificação automatizada

No backend, com as dependências de teste disponíveis:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_copilot_analysis.py tests/test_copilot.py tests/test_budget_policy_review.py tests/test_policy_documents.py tests/test_policy_retrieval.py tests/test_policy_index.py tests/test_policy_embeddings.py tests/test_alerts.py tests/test_dashboard_analytics.py tests/test_workspaces_audit.py
```

Os testes isolam configuração, banco e serviços externos; não usam credenciais,
dados reais nem rede. Validam consulta real no banco temporário, limites de
alertas, preservação das regras, isolamento inclusive com cache de entidades,
ausência de escritas, argumentos proibidos, fonte ausente e indução. A relevância
semântica e a escolha do modelo com Gemini real exigem a avaliação manual acima.
