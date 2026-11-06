import pytest

from app.copilot_schemas import PolicyAnswer, PolicySource
from app.services.policy_retrieval import format_policy_answer


def source():
    return PolicySource(
        source_id="S1",
        document_id="POL-DESP-001",
        version="1.0",
        section_id="DESP-01",
        section_title="Alimentação",
        text="Limite de R$ 80 por pessoa, por refeição.",
        similarity=0.8,
    )


def test_formats_only_known_citations():
    text, ids = format_policy_answer(
        PolicyAnswer(
            supported=True,
            answer="O limite é R$ 80 por pessoa, por refeição.",
            source_ids=["S1", "S1"],
        ),
        [source()],
    )

    assert ids == ["S1"]
    assert "POL-DESP-001, versão 1.0, seção DESP-01" in text
    assert text.count("[S1]") == 1


@pytest.mark.parametrize("ids", [[], ["S99"]])
def test_rejects_missing_or_unknown_citations(ids):
    with pytest.raises(RuntimeError):
        format_policy_answer(
            PolicyAnswer(
                supported=True,
                answer="Resposta de teste.",
                source_ids=ids,
            ),
            [source()],
        )


def test_unsupported_answer_uses_backend_message():
    text, ids = format_policy_answer(
        PolicyAnswer(
            supported=False,
            answer="Texto que não deve ser apresentado.",
            source_ids=["S1"],
        ),
        [source()],
    )

    assert ids == []
    assert "Não encontrei suporte suficiente" in text
    assert "Texto que não deve ser apresentado" not in text


def test_analysis_retrieval_adds_real_references_and_deduplicates(monkeypatch):
    from app.services import policy_retrieval
    original = source()
    monkeypatch.setattr(policy_retrieval, "search_financial_policies", lambda *args: [original])
    required = {("POL-DESP-001", "DESP-01"), ("POL-ORC-001", "ORC-03"), ("POL-TEST-999", "TEST-99")}
    result = policy_retrieval.search_analysis_policies(object(), object(), "Explique o alerta", required)
    assert [(item.document_id, item.section_id) for item in result] == [
        ("POL-DESP-001", "DESP-01"), ("POL-ORC-001", "ORC-03"),
    ]
    assert [item.source_id for item in result] == ["S1", "S2"]
    assert result[1].similarity == 0  # Explicit reference lookup, not semantic score.


def test_analysis_retrieval_does_not_invent_missing_alert_section(monkeypatch):
    from app.services import policy_retrieval
    from app.services.policy_documents import load_policy_chunks
    chunks = [chunk for chunk in load_policy_chunks() if chunk.section_id != "ORC-04"]
    monkeypatch.setattr(policy_retrieval, "load_policy_chunks", lambda: chunks)
    monkeypatch.setattr(policy_retrieval, "search_financial_policies", lambda *args: [source()])
    result = policy_retrieval.search_analysis_policies(object(), object(), "Sem orçamento", {("POL-ORC-001", "ORC-04")})
    assert len(result) == 1
    assert all(item.section_id != "ORC-04" for item in result)


def test_analysis_empty_corpus_is_not_an_index_configuration_error(monkeypatch):
    from app.services import policy_retrieval
    from app.services.policy_documents import EmptyPolicyCorpus
    def empty():
        raise EmptyPolicyCorpus("Nenhum documento Markdown encontrado")
    monkeypatch.setattr(policy_retrieval, "load_policy_chunks", empty)
    assert policy_retrieval.search_analysis_policies(object(), object(), "Resumo", set()) == []


def test_analysis_retrieval_propagates_stale_index(monkeypatch):
    from app.services import policy_retrieval
    def stale(*args):
        raise RuntimeError("Índice ausente ou desatualizado")
    monkeypatch.setattr(policy_retrieval, "search_financial_policies", stale)
    with pytest.raises(RuntimeError, match="desatualizado"):
        policy_retrieval.search_analysis_policies(object(), object(), "Resumo", set())
