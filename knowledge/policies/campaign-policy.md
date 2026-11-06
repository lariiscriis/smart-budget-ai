# Política de Análise de Campanhas — Empresa Aurora Fictícia

Documento: POL-CAMP-001
Versão: 1.0
Vigência inicial: 2026-01-01
Finalidade: demonstração do Smart Budget AI.
Todas as políticas, empresas e procedimentos deste documento são fictícios de demonstração.

## CAMP-01 — Registros da campanha e período

A análise deve identificar uma campanha cadastrada pelo ID ou nome exato e
consultar suas receitas e despesas no espaço de trabalho autenticado e mês
selecionado. Não misturar campanhas com nomes semelhantes nem incluir registros
sem vínculo. Mostrar os totais e quantidades de lançamentos de cada tipo.
Zero registros significa ausência de movimento registrado nesse recorte,
não prova ausência de atividade ou de custos fora do sistema.

## CAMP-02 — Orçamento ou limite interno explícito

Esta política fictícia de demonstração não define valor monetário para limite
de campanha. O sistema deve consultar o orçamento/limite específico cadastrado
para a campanha e o período. Comparar despesas com esse limite somente quando
houver dado explícito, incluindo o escopo temporal do limite.

O cadastro atual de campanhas contém apenas identificação e nome, sem campo
ou relação para esse orçamento. Nesse caso, informar "não há limite definido"
e não calcular desvio ou utilização de limite de campanha.
Orçamento de categoria, total de despesas, valor citado pelo usuário ou número
de outra política não substituem um limite cadastrado para a campanha.
A definição ou cadastro desse limite depende de decisão humana fora do copiloto.

## CAMP-03 — Associação, diferença e custos completos

Receitas registradas com vínculo à campanha são associação cadastral, não
evidência de que a campanha causou essas receitas. Não afirmar causalidade,
incremento de vendas ou retorno causal de investimento sem fonte adequada.

A diferença calculada entre receitas e despesas registradas é apenas saldo
entre esses registros. Não chamá-la de lucro ou rentabilidade sem suporte de
custos completos, incluindo custos diretos, indiretos, taxas e demais custos.
O sistema atual não verifica a completude desses custos; informar essa lacuna.

## CAMP-04 — Documentação e próxima ação

Identificar políticas de despesas e orçamento pertinentes sem concluir que
um alerta de categoria é alerta da campanha. Alertas de orçamento continuam
sob as regras automáticas do backend e os procedimentos POL-ORC-001.

Quando faltarem limite específico, comprovantes, autorizações ou informação
de custos completos, apresentar dúvidas e sugerir reunir esses dados com o
responsável. A comparação é consultiva: não aprova despesas, não altera
orçamentos, não cria lançamentos e não dispara automações.
