from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine
from app.services.policy_documents import load_policy_chunks
from app.services.policy_index import index_policy_chunks


def main() -> None:
    if settings.gemini_api_key is None:
        raise RuntimeError("Configure GEMINI_API_KEY no backend/.env.")

    api_key = settings.gemini_api_key.get_secret_value()

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY está vazia.")

    chunks = load_policy_chunks()

    try:
        with genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=30000),
        ) as client:
            with Session(engine) as db:
                created = index_policy_chunks(db, client, chunks)
                db.commit()

        print(f"Trechos atuais: {len(chunks)}")
        print(f"Novos embeddings: {created}")
        print(f"Embeddings reutilizados: {len(chunks) - created}")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()