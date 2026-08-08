# tests/test_similarity.py
"""Unit tests for the vector codec and pure-Python kNN (no numpy, no ML stack)."""
import math

from arcade_scanner.core.similarity import decode_vector, dot, encode_vector, top_k


def test_roundtrip_preserves_direction():
    blob = encode_vector([3.0, 4.0])
    values = decode_vector(blob)
    assert len(values) == 2
    # encode normalizes: (3,4) → (0.6, 0.8)
    assert math.isclose(values[0], 0.6, abs_tol=1e-6)
    assert math.isclose(values[1], 0.8, abs_tol=1e-6)


def test_encoded_vector_is_unit_length():
    values = decode_vector(encode_vector([1.0, 2.0, 3.0, 4.0]))
    norm = math.sqrt(sum(v * v for v in values))
    assert math.isclose(norm, 1.0, abs_tol=1e-6)


def test_zero_vector_stays_zero():
    values = decode_vector(encode_vector([0.0, 0.0, 0.0]))
    assert values == [0.0, 0.0, 0.0]


def test_blob_is_float32_layout():
    blob = encode_vector([1.0, 0.0])
    assert len(blob) == 8  # 2 × 4 bytes


def test_dot_of_normalized_vectors_is_cosine():
    a = decode_vector(encode_vector([1.0, 0.0]))
    b = decode_vector(encode_vector([1.0, 1.0]))
    assert math.isclose(dot(a, b), math.cos(math.pi / 4), abs_tol=1e-6)


def test_top_k_orders_and_limits():
    query = decode_vector(encode_vector([1.0, 0.0]))
    candidates = [
        ("/lib/same.mp4", decode_vector(encode_vector([1.0, 0.0]))),
        ("/lib/close.mp4", decode_vector(encode_vector([0.9, 0.1]))),
        ("/lib/far.mp4", decode_vector(encode_vector([0.0, 1.0]))),
    ]
    results = top_k(query, candidates, k=2, exclude=set())
    assert [p for p, _ in results] == ["/lib/same.mp4", "/lib/close.mp4"]
    assert results[0][1] >= results[1][1]


def test_top_k_excludes_paths():
    query = decode_vector(encode_vector([1.0, 0.0]))
    candidates = [
        ("/lib/query.mp4", query),
        ("/lib/other.mp4", decode_vector(encode_vector([0.5, 0.5]))),
    ]
    results = top_k(query, candidates, k=5, exclude={"/lib/query.mp4"})
    assert [p for p, _ in results] == ["/lib/other.mp4"]


def test_top_k_empty_candidates():
    assert top_k([1.0], [], k=3, exclude=set()) == []
