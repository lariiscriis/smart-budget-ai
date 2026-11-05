from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import PolicyEmbedding
from app.services import policy_index
from app.services.policy_documents import PolicyChunk
from app.services.policy_embeddings import EMBEDDING_DIMENSIONS


def make_chunk(chunk_id: str) -> PolicyChunk:
    return PolicyChunk(
        chunk_id=chunk_id,
        document_id="POL-TEST-001",
        document_title="Política de Teste",
        version="1.0",
        effective_from=date(2026, 1, 1),
        section_id="TEST-01",
        section_title="Alimentação",
        text="O limite é de R$ 80 por refeição.",
        source_file="test-policy.md",
    )


def test_cache_identity_includes_model_and_dimensions():
    original = policy_index.embedding_cache_key("chunk", "model-a", 768)

    assert original == policy_index.embedding_cache_key(
        "chunk", "model-a", 768
    )
    assert original != policy_index.embedding_cache_key(
        "chunk", "model-b", 768
    )
    assert original != policy_index.embedding_cache_key(
        "chunk", "model-a", 3072
    )


def test_saved_embeddings_are_reused(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    PolicyEmbedding.__table__.create(engine)

    calls = []
    vector = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)

    def fake_embed(client, texts, task_type):
        calls.append((texts, task_type))
        return [vector.copy() for _ in texts]

    monkeypatch.setattr(policy_index, "embed_texts", fake_embed)

    try:
        with Session(engine) as db:
            created = policy_index.index_policy_chunks(
                db, object(), [make_chunk("a" * 64)]
            )
            db.commit()
            assert created == 1

        with Session(engine) as db:
            created = policy_index.index_policy_chunks(
                db, object(), [make_chunk("a" * 64)]
            )
            vectors = policy_index.load_document_vectors(
                db, [make_chunk("a" * 64)]
            )

            assert created == 0
            assert vectors == [vector]

            with pytest.raises(RuntimeError, match="desatualizado"):
                policy_index.load_document_vectors(
                    db, [make_chunk("b" * 64)]
                )

        assert len(calls) == 1
        assert calls[0][1] == "RETRIEVAL_DOCUMENT"

    finally:
        engine.dispose()