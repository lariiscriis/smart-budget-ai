import argparse

from google import genai
from google.genai import types

from app.config import settings
from app.services.policy_documents import load_policy_chunks
from app.services.policy_embeddings import embed_texts, similarity
from sqlalchemy.orm import Session

from app.database import engine
from app.services.policy_index import load_document_vectors

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Busca experimental nas políticas fictícias."
    )
    parser.add_argument("question")
    args = parser.parse_args()

    question = args.question.strip()

    if not question:
        parser.error("A pergunta não pode ser vazia.")

    if settings.gemini_api_key is None:
        raise RuntimeError("Configure GEMINI_API_KEY no backend/.env.")

    api_key = settings.gemini_api_key.get_secret_value()

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY está vazia.")

    chunks = load_policy_chunks()

    try:
        with Session(engine) as db:
            document_vectors = load_document_vectors(db, chunks)
    finally:
        engine.dispose()

    with genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=30000),
    ) as client:

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

    print(f"Pergunta: {question}")
    print(f"Trechos consultados: {len(chunks)}")

    for position, (score, chunk) in enumerate(ranked[:3], start=1):
        print(
            f"\n{position}. Similaridade: {score:.4f}\n"
            f"Fonte: {chunk.document_id}, versão {chunk.version}, "
            f"seção {chunk.section_id}\n"
            f"Título: {chunk.section_title}\n"
            f"{chunk.text}"
        )


if __name__ == "__main__":
    main()