import hashlib
import json

from google import genai
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PolicyEmbedding
from app.services.policy_documents import PolicyChunk
from app.services.policy_embeddings import (
    EMBEDDING_DIMENSIONS,
    embed_texts,
    normalize_vector,
)


INDEX_FORMAT_VERSION = "1"


def embedding_cache_key(
    chunk_id: str,
    model_name: str,
    dimensions: int,
) -> str:
    identity = json.dumps(
        {
            "chunk_id": chunk_id,
            "model_name": model_name,
            "dimensions": dimensions,
            "task_type": "RETRIEVAL_DOCUMENT",
            "index_format_version": INDEX_FORMAT_VERSION,
        },
        sort_keys=True,
    )

    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def document_text(chunk: PolicyChunk) -> str:
    return (
        f"{chunk.document_title}\n"
        f"{chunk.section_id} — {chunk.section_title}\n"
        f"{chunk.text}"
    )


def index_policy_chunks(
    db: Session,
    client: genai.Client,
    chunks: list[PolicyChunk],
) -> int:
    pending = []

    for chunk in chunks:
        key = embedding_cache_key(
            chunk.chunk_id,
            settings.gemini_embedding_model,
            EMBEDDING_DIMENSIONS,
        )

        if db.get(PolicyEmbedding, key) is None:
            pending.append((key, chunk))

    if not pending:
        return 0

    vectors = embed_texts(
        client,
        [document_text(chunk) for _, chunk in pending],
        "RETRIEVAL_DOCUMENT",
    )

    for (key, chunk), vector in zip(pending, vectors, strict=True):
        db.add(
            PolicyEmbedding(
                cache_key=key,
                chunk_id=chunk.chunk_id,
                model_name=settings.gemini_embedding_model,
                dimensions=EMBEDDING_DIMENSIONS,
                vector=vector,
            )
        )

    db.flush()
    return len(pending)


def load_document_vectors(
    db: Session,
    chunks: list[PolicyChunk],
) -> list[list[float]]:
    vectors = []

    for chunk in chunks:
        key = embedding_cache_key(
            chunk.chunk_id,
            settings.gemini_embedding_model,
            EMBEDDING_DIMENSIONS,
        )

        row = db.get(PolicyEmbedding, key)

        if row is None:
            raise RuntimeError(
                f"Índice ausente ou desatualizado para {chunk.section_id}. "
                "Execute python -m app.index_policies."
            )

        if (
            row.chunk_id != chunk.chunk_id
            or row.model_name != settings.gemini_embedding_model
            or row.dimensions != EMBEDDING_DIMENSIONS
            or len(row.vector) != EMBEDDING_DIMENSIONS
        ):
            raise RuntimeError(
                f"Embedding incompatível para {chunk.section_id}."
            )

        vectors.append(normalize_vector(row.vector))

    return vectors