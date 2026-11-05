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