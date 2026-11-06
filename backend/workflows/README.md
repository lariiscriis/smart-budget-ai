# Resumo automático com políticas da Aurora

Este diretório mantém **um único workflow**, `SmartBudget - Resumo e alertas.json`.
Ele foi atualizado, sem criar outro fluxo nem enviar notificações externas.
As políticas de demonstração existentes não foram alteradas.

## Funcionamento

1. A confirmação de uma importação válida grava despesas, conclui o lote e
   enfileira um `AutomationJob` por mês do arquivo na mesma transação. A
   confirmação repetida e a restrição única por lote/período impedem nova fila.
2. O worker bloqueia um job `pending`, registra `running` e incrementa
   `attempts`. Envia ao webhook `job_id`, `import_id`, `workspace_id`, ano,
   mês, tentativa, `actor_kind=automation` e uma credencial temporária.
3. O workflow usa essa credencial em `Authorization: Bearer ...` e consulta
   `GET /automations/{job_id}/analysis`, encaminhando ano, mês, espaço, importação
   e tentativa. A identidade vem da credencial; os parâmetros apenas confirmam
   o contexto. Valores divergentes são rejeitados, sem trocar o workspace.
4. O backend chama diretamente `review_budget_policy` com `focus=decision`:
   comparação financeira, alertas determinísticos, analytics e RAG. Não há
   seleção livre de ferramentas pelo modelo, SQL do modelo ou ações financeiras.
   A resposta separa números, regras recuperadas, dúvidas, riscos e sugestões
   para revisão humana. Os números abrangem o mês do workspace, incluindo os
   outros lançamentos; não são totais exclusivos do arquivo importado.
5. A análise é armazenada em `AutomationJob.result` sob bloqueio da linha antes
   da resposta HTTP. Repetições usam essa cópia, inclusive após perda da resposta.
   O n8n somente devolve o JSON do backend; não calcula nem modifica a análise.
6. O worker valida schema, período, contexto e igualdade com a cópia persistida.
   Só então marca `succeeded`; falhas deixam `failed` e `last_error` sanitizado.
   A credencial é revogada ao finalizar. Mudanças operacionais registram
   `actor_kind=automation` na auditoria, sem copiar tokens ou resultados para o log.

Não há aprovação de despesas/reembolsos, alteração de orçamento ou lançamento,
notificação externa ou acionamento de outra automação. As únicas gravações são
de controle da tarefa, sua análise, credencial temporária e auditoria operacional.

## Preparar o backend

Os comandos abaixo são para PowerShell, dentro de `backend`, usando um ambiente
Python 3.12 funcional com as dependências do projeto. Se o `.venv` mostrar
“No Python at…”, corrija esse ambiente antes de executar os comandos.

Configure `AI_MODE=gemini`, `GEMINI_API_KEY` e os dados de conexão ao banco no
ambiente local já usado pelo backend. Não copie chaves para o workflow.
Atualize o índice se ainda não estiver atualizado:

```powershell
.\.venv\Scripts\python.exe -m app.index_policies
```

O índice é uma operação administrativa separada; a análise somente consulta
os embeddings documentais existentes. `AI_MODE=mock`, falta de chave, índice
desatualizado ou indisponibilidade do provedor deixam o job em falha para retry,
sem inventar regras. Se o corpus realmente não possuir políticas, a análise
mostra essa ausência preservando os fatos financeiros disponíveis.

Mantenha o backend na porta 8000. O banco continua usando a migração existente;
não foi acrescentada migração ou tabela nesta tarefa.

## Atualizar/importar e ativar no n8n local

1. Abra `http://localhost:5678` e o workflow **SmartBudget - Resumo e alertas**.
   Pause sua publicação/ativação antes de substituir a versão antiga.
2. Atualize esse mesmo workflow com o JSON deste diretório. Se **… → Import from
   File** da sua versão substituir o conteúdo no editor atual, selecione o
   arquivo. Se essa ação criar outro workflow, prefira copiar o conteúdo JSON
   do arquivo e colá-lo diretamente no canvas do workflow existente, substituindo
   os nós antigos. Confira as configurações do passo 5, pois copiar nós pode
   não copiar configurações do workflow. Use a importação como novo fluxo apenas
   em uma instalação que ainda não tenha esse workflow. Não mantenha dois
   fluxos ativos para a mesma rota.
3. Confira o encadeamento: **Entrada → Resumo Financeiro → Respond to Webhook**.
   O nó de resumo chama `/automations/{job_id}/analysis` e encaminha todos os
   parâmetros e o Bearer dinâmico. Não configure uma chave Gemini no n8n.
4. Se o n8n estiver em Docker e o backend no Windows, troque apenas o host da
   expressão da URL HTTP para `http://host.docker.internal:8000`. Sem Docker,
   mantenha `http://127.0.0.1:8000`.
5. Confira em **Settings**: não salvar execuções de sucesso, falha, manuais ou
   progresso dos nós. O JSON já traz essas opções e nenhum dado fixado
   (`pinData`). Isso evita persistir o token recebido pelo webhook no histórico.
   Não habilite logs de payloads/headers ou debug HTTP para esse fluxo.
6. Publique pelo botão **Publish**; em versões antigas, salve e habilite
   **Active/Ativo**. O JSON fica desativado até essa etapa explícita.
7. Use a **Production URL** do webhook, normalmente:
   `http://localhost:5678/webhook/smartbudget-summary`. Configure essa URL em
   `N8N_WEBHOOK_URL` no ambiente do worker. Não use `/webhook-test/` para o worker.

Referências oficiais: [importação de JSON](https://docs.n8n.io/workflows/export-import/),
[publicação](https://docs.n8n.io/build/understand-workflows/save-and-publish-workflows.md)
e [configurações de execução](https://docs.n8n.io/workflows/settings/).

## Iniciar o processamento automático

Em outro terminal, dentro de `backend`:

```powershell
.\.venv\Scripts\python.exe -m app.automation_worker --watch --poll-seconds 5
```

Enquanto esse processo estiver ativo, novas importações concluídas são coletadas
da fila a cada ciclo. `Ctrl+C` interrompe o worker preservando os jobs no banco.
Para um teste de processamento único, sem ficar observando a fila:

```powershell
.\.venv\Scripts\python.exe -m app.automation_worker --limit 1
```

Não é necessário iniciar o worker dentro de uma requisição de importação nem
manter o n8n disponível durante o upload: a fila é persistida no banco primeiro.

## Verificar sucesso

1. No aplicativo autenticado, importe e **confirme** um CSV fictício válido.
   Fazer somente a prévia não cria a tarefa. Arquivo com vários meses cria um
   job por mês, sem repetir os períodos.
2. Na aba **Automações**, atualize a listagem. O job passa de `pending` para
   `running` e `succeeded`; o terminal também informa ID e status, sem tokens.
3. Expanda o resultado JSON já disponível nessa tela ou consulte `GET /automations`
   com a sessão autenticada. Confira `result.schema_version=2.0`, contexto,
   `summary`, `alerts` e `analysis.answer`. Em `analysis.tools_used[0]`, confira
   `focus=decision`, evidências, fontes e referências citadas.
4. Compare números com o dashboard do mesmo mês/espaço. Uma lista de alertas
   vazia não comprova conformidade de despesas. As sugestões não são aprovações.
5. Confirme novamente a mesma importação: a resposta deve informar
   `already_completed=true`, sem novas despesas nem novo job. Rodar novamente o
   worker não reprocessa jobs `succeeded`.

O histórico detalhado do n8n está desabilitado para esse fluxo; a evidência
persistente da execução é o `AutomationJob` e sua auditoria no backend.

## Verificar falha e retry

1. Com o worker parado, desligue o n8n e confirme uma **nova** importação fictícia.
2. Execute o worker com `--limit 1`. O mesmo job fica `failed`, com `attempts=1`
   e `last_error` contendo apenas uma classe como `ConnectError`. Os dados
   importados continuam salvos e o job continua disponível.
3. Ligue o n8n e publique/ative o workflow atualizado.
4. Na aba **Automações**, use **Recolocar na fila** no job com falha
   (ou `POST /automations/{job_id}/retry` com sessão e CSRF habituais).
   O job volta a `pending`. Um segundo retry enquanto está pendente retorna 409.
5. Execute o worker outra vez. O **mesmo ID** termina em `succeeded`, agora com
   `attempts=2`, sem duplicar as despesas ou a importação. Cada tentativa usa
   uma nova credencial; a anterior deixa de funcionar.

Se a análise foi salva e apenas a resposta do n8n se perdeu, o retry preserva
e reutiliza a análise em `result`, atualizando o contexto da tentativa. O retrato
financeiro/documental é o da primeira geração, não uma nova avaliação do mês.
Se o processo do worker caiu enquanto `running`, uma execução posterior do
worker recupera jobs sem atualização há 5 minutos como `failed`, com erro
`WorkerLeaseExpired`; depois use o mesmo retry. Respostas de tentativas antigas
não podem sobrescrever uma tentativa mais recente. Não existe promessa de
entrega HTTP exatamente uma vez; a fila única, o cache e o controle de tentativa
impedem duplicação persistente. O cache só existe após uma geração concluída;
uma queda anterior ao commit pode exigir repetir a consulta de leitura ao RAG.

## Verificações automatizadas

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_automation_jobs.py tests/test_automation_policy_flow.py tests/test_auth_security.py tests/test_workspaces_audit.py tests/test_copilot_analysis.py
```

Os testes usam SQLite isolado, RAG/provedor simulado e uma ponte HTTP simulando
o n8n. Cobrem sucesso, duplicação de confirmação, múltiplos meses, perda de
resposta, cache, retry, interrupção, contexto divergente, isolamento, alteração
indevida da resposta, revogação de credencial e sanitização de erros.
Uma execução contra o n8n e o MySQL locais deve ser verificada pelos passos acima.
