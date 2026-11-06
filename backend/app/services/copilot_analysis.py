"""Read-only evidence and backend-rendered decision boundaries for the copilot.

The model selects a typed query. It cannot supply monetary values, workspace
identity, approvals or SQL, and does not author the resulting factual narrative.
Document excerpts and record labels remain reference content, never commands.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.copilot_schemas import (
    AnalysisEvidence, CampaignReviewArguments, ExpenseEvidence,
    ExpenseReviewArguments, ToolExecution,
)
from app.models import Campaign, Category, Expense
from app.services.dashboard import get_dashboard_analytics, next_month


ALERT_SECTIONS = {
    "near_limit": "ORC-02", "over_budget": "ORC-03", "unbudgeted": "ORC-04",
}

EXPENSE_GAPS = [
    "Comprovante verificável (não há campo no cadastro).",
    "Finalidade profissional e autorização verificadas (a descrição é apenas texto declarado).",
    "Quantidade de pessoas e refeições, se alimentação; pessoas e diárias, se hospedagem.",
    "Origem e destino, se transporte por aplicativo.",
    "Data da solicitação de reembolso para avaliar o prazo documental, se recuperado.",
]
CAMPAIGN_GAPS = [
    "Não há limite definido: o cadastro atual não possui orçamento/limite específico de campanha.",
    "Completude dos custos diretos, indiretos, taxas e demais custos não verificada.",
    "Evidência de atribuição causal da receita à campanha não disponível.",
]


def require_workspace(db: Session) -> int:
    workspace_id = db.info.get("workspace_id")
    if workspace_id is None:
        raise RuntimeError("An authenticated workspace is required for financial queries.")
    return workspace_id


def consult_expense(db: Session, args: ExpenseReviewArguments) -> AnalysisEvidence:
    workspace_id = require_workspace(db)
    if args.expense_id is None:
        return AnalysisEvidence(status="missing_identifier", missing_data=[
            "Informe o ID da despesa existente e selecione o mês do lançamento.",
        ])
    # select, rather than Session.get, also enforces scope for an identity-map hit.
    row = db.execute(select(Expense, Category.name).join(
        Category, (Expense.category_id == Category.id)
        & (Expense.workspace_id == Category.workspace_id),
    ).where(
        Expense.workspace_id == workspace_id, Expense.id == args.expense_id,
        Expense.expense_date >= date(args.year, args.month, 1),
        Expense.expense_date < next_month(args.year, args.month),
    )).one_or_none()
    if row is None:
        return AnalysisEvidence(status="not_found", missing_data=[
            "Despesa não encontrada no espaço de trabalho e período selecionados; confirme o ID e o mês.",
        ])
    expense, category_name = row
    return AnalysisEvidence(expense=ExpenseEvidence(
        id=expense.id, category_id=expense.category_id, category_name=category_name,
        campaign_id=expense.campaign_id, description=expense.description,
        expense_date=expense.expense_date, amount=expense.amount,
    ), missing_data=EXPENSE_GAPS)


def consult_campaign(db: Session, args: CampaignReviewArguments) -> AnalysisEvidence:
    workspace_id = require_workspace(db)
    if args.campaign_id is None and args.campaign_name is None:
        return AnalysisEvidence(status="missing_identifier", missing_data=[
            "Informe o ID ou o nome exato da campanha cadastrada.",
        ])
    query = select(Campaign).where(Campaign.workspace_id == workspace_id)
    if args.campaign_id is not None:
        query = query.where(Campaign.id == args.campaign_id)
    if args.campaign_name is not None:
        query = query.where(Campaign.name == args.campaign_name)
    matches = db.scalars(query).all()
    # Database collations may equate accents/case. Do not guess a name match.
    if args.campaign_name is not None:
        matches = [item for item in matches if item.name == args.campaign_name]
    if len(matches) != 1:
        return AnalysisEvidence(status="ambiguous" if matches else "not_found", missing_data=[
            "Campanha não identificada de forma única no espaço de trabalho; confirme o ID ou nome exato.",
        ])
    campaign = matches[0]
    analytics = get_dashboard_analytics(db, args.year, args.month, months=1)
    totals = next((item for item in analytics.campaigns if item.campaign_id == campaign.id), None)
    if totals is None:
        from app.dashboard_schemas import CampaignAnalytics
        totals = CampaignAnalytics(
            campaign_id=campaign.id, campaign_name=campaign.name,
            income=Decimal("0.00"), expenses=Decimal("0.00"), balance=Decimal("0.00"),
            income_count=0, expense_count=0,
        )
    return AnalysisEvidence(campaign=totals, missing_data=CAMPAIGN_GAPS)


def link_alert_policies(execution: ToolExecution) -> None:
    """Link computed alerts only to an actually retrieved matching section."""
    execution.evidence.alert_policy_sources = {
        str(alert.category_id): [source.source_id for source in execution.sources
            if source.document_id == "POL-ORC-001"
            and source.section_id == ALERT_SECTIONS[alert.code]]
        for alert in execution.alerts
    }


def record_missing_sections(evidence: AnalysisEvidence, sources, required_sections) -> None:
    present = {(source.document_id, source.section_id) for source in sources}
    evidence.missing_data.extend(
        f"Política não recuperada: {document_id}, seção {section_id}."
        for document_id, section_id in sorted(required_sections - present)
    )


def render_analysis(execution: ToolExecution) -> str:
    """Do not ask the model to invent a narrative when evidence is incomplete."""
    args, evidence = execution.arguments, execution.evidence
    lines = [f"Análise de {args.month:02d}/{args.year} — dados do espaço de trabalho autenticado."]
    if evidence.expense:
        item = evidence.expense
        lines += ["Evidências cadastradas (conteúdo declarado, sem validação documental):",
                  f"- Despesa #{item.id}; data {item.expense_date}; valor BRL {item.amount}.",
                  f"- Categoria #{item.category_id}: {item.category_name!r}.",
                  f"- Descrição: {item.description!r}; campanha: {item.campaign_id}."]
    if evidence.campaign:
        item = evidence.campaign
        lines += [f"Campanha #{item.campaign_id}: {item.campaign_name!r}.",
                  f"Receitas registradas: BRL {item.income} ({item.income_count} lançamentos).",
                  f"Despesas registradas: BRL {item.expenses} ({item.expense_count} lançamentos).",
                  f"Diferença entre registros: BRL {item.balance}.",
                  "Sem comparação com limite: não há limite definido no cadastro de campanha.",
                  "A associação dos registros não demonstra que a campanha causou a receita. "
                  "A diferença não é lucro: a completude dos custos não foi demonstrada."]
    if execution.result:
        summary = execution.result
        lines += [f"Orçamento de despesas: previsto BRL {summary.planned}; "
                  f"realizado BRL {summary.actual}; saldo orçamentário BRL {summary.balance}; "
                  f"utilização {summary.utilization_percentage if summary.utilization_percentage is not None else 'não se aplica'}" +
                  ("%." if summary.utilization_percentage is not None else ".")]
        lines += [f"- Categoria #{item.category_id} {item.category_name!r}: previsto BRL {item.summary.planned}; "
                  f"realizado BRL {item.summary.actual}; saldo BRL {item.summary.balance}."
                  for item in execution.categories]
    if evidence.analytics:
        totals = evidence.analytics
        lines += [f"Receitas registradas: BRL {totals.income_total}; despesas: BRL {totals.expense_total}; "
                  f"saldo entre registros: BRL {totals.cash_balance} (não comprova lucro)."]
        lines += [f"- Campanha {item.campaign_name!r} (ID {item.campaign_id}): receitas BRL {item.income}; "
                  f"despesas BRL {item.expenses}; diferença BRL {item.balance}."
                  for item in totals.campaigns]
    if execution.result:
        lines.append("Alertas calculados pelo backend — regras automáticas de orçamento, distintas da política interna:")
        for alert in execution.alerts:
            ids = evidence.alert_policy_sources.get(str(alert.category_id), [])
            reference = ", ".join(f"[{source_id}]" for source_id in ids) if ids else "política pertinente não recuperada"
            lines.append(f"- {alert.category_name!r}: {alert.code} ({alert.severity}) — {alert.message} "
                         f"Previsto BRL {alert.planned}; realizado BRL {alert.actual}; saldo BRL {alert.balance}. "
                         f"Orientação documental: {reference}.")
        if not execution.alerts:
            lines.append("Nenhuma categoria atingiu as regras atuais; isso não comprova conformidade dos reembolsos.")
    lines.append("Regras documentais recuperadas para análise (políticas fictícias de demonstração):")
    for source in execution.sources:
        lines.append(f"[{source.source_id}] {source.document_id}, versão {source.version}, seção {source.section_id} "
                     f"— {source.section_title}\nTrecho documental de referência: {source.text}")
    if not execution.sources:
        lines.append("Política ausente na recuperação: não há suporte documental para concluir quais regras internas se aplicam.")
    elif execution.name == "compare_campaign_policy" and not any(
        source.document_id == "POL-CAMP-001" for source in execution.sources
    ):
        lines.append("Política de campanha ausente na recuperação; as demais fontes não definem seu limite interno.")
    elif execution.name == "review_expense_policy" and not any(
        source.document_id == "POL-DESP-001" for source in execution.sources
    ):
        lines.append("Política de despesas ausente na recuperação; não há suporte para avaliar suas regras específicas.")
    lines.append("A aplicabilidade das regras depende do contexto e das evidências; a vigência histórica não foi validada.")
    lines.append("Dúvidas e dados faltantes:")
    lines.extend(f"- {gap}" for gap in evidence.missing_data)
    lines += ["Riscos e limites: registros e descrições não comprovam autorização ou documentação; "
              "não é possível declarar conformidade definitiva, aprovar reembolso ou atribuir causas aos desvios.",
              "Sugestões de próxima ação (decisão humana): confirmar a classificação e a finalidade dos registros; "
              "reunir comprovantes e autorizações; esclarecer as lacunas com o responsável. "
              "Para alertas, considerar revisar despesas e justificar o desvio com base na regra citada. "
              "Para campanhas, solicitar o limite interno cadastrado e a relação completa de custos.",
              "Esta análise é consultiva: não grava, aprova, altera orçamento nem dispara automações."]
    execution.cited_source_ids = [source.source_id for source in execution.sources]
    return "\n\n".join(lines)
