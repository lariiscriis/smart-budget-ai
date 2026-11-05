import pytest

from app.services.policy_embeddings import (
    normalize_vector,
    similarity,
)


def test_normalizes_vector():
    result = normalize_vector([3.0, 4.0])

    assert result == pytest.approx([0.6, 0.8])


def test_similarity_ignores_vector_magnitude():
    assert similarity(
        [1.0, 0.0],
        [5.0, 0.0],
    ) == pytest.approx(1.0)


def test_perpendicular_vectors_have_zero_similarity():
    assert similarity(
        [1.0, 0.0],
        [0.0, 1.0],
    ) == pytest.approx(0.0)


@pytest.mark.parametrize(
    "values",
    [
        [],
        [0.0, 0.0],
        [float("nan"), 1.0],
        [float("inf"), 1.0],
    ],
)
def test_rejects_invalid_vectors(values):
    with pytest.raises(ValueError):
        normalize_vector(values)


def test_rejects_different_dimensions():
    with pytest.raises(ValueError, match="dimensões diferentes"):
        similarity([1.0], [1.0, 2.0])