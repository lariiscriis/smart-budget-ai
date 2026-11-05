import math
from typing import Literal

from google import genai
from google.genai import types

from app.config import settings


EMBEDDING_DIMENSIONS = 768

EmbeddingTask = Literal[
    "RETRIEVAL_DOCUMENT",
    "RETRIEVAL_QUERY",
]


def normalize_vector(values: list[float]) -> list[float]:
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("O vetor deve conter números finitos.")

    magnitude = math.sqrt(sum(value * value for value in values))

    if magnitude == 0 or not math.isfinite(magnitude):
        raise ValueError("O vetor possui magnitude inválida.")

    return [value / magnitude for value in values]


def similarity(
    first: list[float],
    second: list[float],
) -> float:
    if len(first) != len(second):
        raise ValueError("Os vetores possuem dimensões diferentes.")

    first_normalized = normalize_vector(first)
    second_normalized = normalize_vector(second)

    return sum(
        left * right
        for left, right in zip(
            first_normalized,
            second_normalized,
            strict=True,
        )
    )


def embed_texts(
    client: genai.Client,
    texts: list[str],
    task_type: EmbeddingTask,
) -> list[list[float]]:
    if not texts or any(not text.strip() for text in texts):
        raise ValueError("Informe pelo menos um texto não vazio.")

    response = client.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )

    embeddings = response.embeddings or []

    if len(embeddings) != len(texts):
        raise RuntimeError(
            "A quantidade de embeddings difere da quantidade de textos."
        )

    vectors = []

    for embedding in embeddings:
        values = embedding.values

        if values is None or len(values) != EMBEDDING_DIMENSIONS:
            raise RuntimeError("O embedding retornou dimensões inesperadas.")

        vectors.append(normalize_vector(list(values)))

    return vectors