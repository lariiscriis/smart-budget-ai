import pytest

from app.services.policy_documents import (
    load_policy_chunks,
    parse_policy,
)


POLICY = """# Política de Teste

Documento: POL-TEST-001
Versão: 1.0
Vigência inicial: 2026-01-01

## TEST-01 — Alimentação

O limite é de R$ 80,00 por pessoa, por refeição.

É obrigatório apresentar comprovante.

## TEST-02 — Multas

Multas não são reembolsáveis.
"""


def test_preserves_metadata_and_complete_section():
    chunks = parse_policy(POLICY, "test-policy.md")

    assert len(chunks) == 2

    first = chunks[0]

    assert first.document_id == "POL-TEST-001"
    assert first.version == "1.0"
    assert first.effective_from.isoformat() == "2026-01-01"
    assert first.section_id == "TEST-01"
    assert first.section_title == "Alimentação"
    assert first.source_file == "test-policy.md"

    assert "R$ 80,00 por pessoa, por refeição" in first.text
    assert "É obrigatório apresentar comprovante." in first.text
    assert "Multas" not in first.text


def test_chunk_identity_changes_when_rule_changes():
    original = parse_policy(POLICY, "test-policy.md")
    repeated = parse_policy(POLICY, "test-policy.md")

    changed = parse_policy(
        POLICY.replace("80,00", "90,00"),
        "test-policy.md",
    )

    assert original[0].chunk_id == repeated[0].chunk_id
    assert original[0].chunk_id != changed[0].chunk_id
    assert original[1].chunk_id == changed[1].chunk_id


def test_rejects_missing_metadata():
    invalid = POLICY.replace("Versão: 1.0\n", "")

    with pytest.raises(ValueError, match="Versão"):
        parse_policy(invalid, "test-policy.md")


def test_rejects_duplicate_sections():
    invalid = POLICY.replace("TEST-02", "TEST-01")

    with pytest.raises(ValueError, match="seção repetida"):
        parse_policy(invalid, "test-policy.md")


def test_loader_reads_files_and_rejects_duplicate_documents(tmp_path):
    (tmp_path / "first.md").write_text(POLICY, encoding="utf-8")

    chunks = load_policy_chunks(tmp_path)

    assert len(chunks) == 2
    assert chunks[0].source_file == "first.md"

    (tmp_path / "second.md").write_text(POLICY, encoding="utf-8")

    with pytest.raises(ValueError, match="Documento e versão repetidos"):
        load_policy_chunks(tmp_path)