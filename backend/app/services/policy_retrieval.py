from google import genai
from sqlalchemy.orm import Session

from app.copilot_schemas import PolicyAnswer, PolicySource
from app.services.policy_documents import load_policy_chunks
from app.services.policy_embeddings import embed_texts, similarity
from app.services.policy_index import load_document_vectors


def search_financial_policies(
    db: Session,
    client: genai.Client,
    question: str,
) -> list[PolicySource]:
    if not question.strip():
        raise ValueError("A pergunta não pode ser vazia.")

    chunks = load_policy_chunks()
    document_vectors = load_document_vectors(db, chunks)

    query_vector = embed_texts(
        client,
        [question],
        "RETRIEVAL_QUERY",
    )[0]

    ranked = sorted(
        [
            (similarity(query_vector, vector), chunk)
            for chunk, vector in zip(
                chunks,
                document_vectors,
                strict=True,
            )
        ],
        key=lambda item: (-item[0], item[1].chunk_id),
    )

    return [
        PolicySource(
            source_id=f"S{position}",
            document_id=chunk.document_id,
            version=chunk.version,
            section_id=chunk.section_id,
            section_title=chunk.section_title,
            text=chunk.text,
            similarity=score,
        )
        for position, (score, chunk) in enumerate(
            ranked[:3],
            start=1,
        )
    ]


def format_policy_answer(
    answer: PolicyAnswer,
    sources: list[PolicySource],
) -> tuple[str, list[str]]:
    if not answer.supported:
        return (
            "Não encontrei suporte suficiente nos dados e nos trechos "
            "recuperados para responder à análise solicitada. "
            "Isso não comprova que a informação inexista em outras fontes.",
            [],
        )

    by_id = {source.source_id: source for source in sources}
    cited_ids = list(dict.fromkeys(answer.source_ids))

    if not cited_ids:
        raise RuntimeError("A resposta documental não informou fontes.")

    if any(source_id not in by_id for source_id in cited_ids):
        raise RuntimeError("A resposta documental citou uma fonte desconhecida.")

    references = "\n".join(
        (
            f"[{source_id}] {by_id[source_id].document_id}, "
            f"versão {by_id[source_id].version}, "
            f"seção {by_id[source_id].section_id} "
            f"— {by_id[source_id].section_title}"
        )
        for source_id in cited_ids
    )

    return (
        f"{answer.answer.strip()}\n\nFontes:\n{references}",
        cited_ids,
    )