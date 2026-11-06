# Política de Acompanhamento Orçamentário — Empresa Aurora Fictícia

Documento: POL-ORC-001
Versão: 1.1
Vigência inicial: 2026-01-01
Finalidade: demonstração do Smart Budget AI.
Todos os procedimentos deste documento são fictícios.

## ORC-01 — Responsabilidade pelos cálculos

Previsto, realizado, saldo e utilização devem ser obtidos
pelas ferramentas financeiras do Smart Budget AI.

O texto da política não substitui os dados financeiros.

## ORC-02 — Aproximação do limite

Categorias com orçamento positivo e realizado entre 80% e 100%
do previsto, incluindo os dois limites, exigem acompanhamento
do responsável pela categoria.

Essa situação corresponde ao alerta near_limit.

## ORC-03 — Orçamento ultrapassado

Quando o realizado supera o orçamento positivo da categoria,
o responsável deve revisar as despesas e justificar o desvio.

Essa situação corresponde ao alerta over_budget.

O alerta não identifica, por si só, a causa do desvio.

## ORC-04 — Despesa sem orçamento

Quando uma categoria possui previsto igual a zero e realizado
positivo, o responsável deve revisar a classificação da despesa
e verificar a necessidade de orçamento.

Essa situação corresponde ao alerta unbudgeted.

O alerta não comprova fraude nem autoriza alterações automáticas.

## ORC-05 — Alterações e aprovações

Um alerta não altera o orçamento e não aprova despesas.

Aprovações e alterações exigem decisão humana fora do copiloto
nesta versão do sistema.

## ORC-06 — Ausência de alertas

A ausência de alertas significa apenas que nenhuma categoria
atingiu as regras implementadas.

Ela não comprova que todas as despesas respeitam a política
de reembolso.

## ORC-07 — Limite da política

Este documento não define regras de impostos, retenção de notas,
adiantamentos ou conversão de moedas.

Perguntas sobre esses assuntos exigem outra fonte.

## ORC-08 — Explicação de alertas e origem das regras

Política fictícia de demonstração da Aurora. A classificação de alertas é
determinística e pertence ao backend: unbudgeted quando previsto é zero e
realizado é positivo; over_budget quando realizado supera previsto positivo;
near_limit quando realizado está entre 80% e 100% do previsto positivo,
inclusive. Os critérios existentes não são modificados por este documento.

A explicação deve usar o alerta calculado e seus valores, preservando código
e severidade. Não recalcular, inferir outro alerta ou aceitar um alerta
alegado na pergunta como fato. Se não houver alertas calculados, informar isso.

ORC-02, ORC-03 e ORC-04 estabelecem procedimentos internos associados a esses
códigos; são orientações documentais distintas da condição automática.
Relacionar cada alerta somente à seção pertinente efetivamente recuperada.
Sem essa seção, mostrar o fato calculado e indicar política não recuperada;
não inventar uma regra interna. Um alerta não determina causa, fraude,
conformidade de reembolso ou autorização para agir.
