# arcade_scanner/core/similarity.py
"""Vector codec + brute-force kNN for the embedding foundation.

Pure stdlib (struct) — the server must not depend on numpy or the ML stack.
Vectors are L2-normalized at encode time, so similarity is a plain dot
product. At library scale (a few thousand mean vectors) brute force answers
in milliseconds.
"""
from __future__ import annotations

import math
import struct
from typing import Iterable, Sequence


def encode_vector(values: Sequence[float]) -> bytes:
    """L2-normalize and pack as little-endian float32 blob."""
    norm = math.sqrt(sum(v * v for v in values))
    if norm > 0:
        values = [v / norm for v in values]
    else:
        values = list(values)
    return struct.pack(f"<{len(values)}f", *values)


def decode_vector(blob: bytes) -> list[float]:
    """Unpack a little-endian float32 blob."""
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def top_k(query: Sequence[float],
          candidates: Iterable[tuple[str, Sequence[float]]],
          k: int,
          exclude: set[str]) -> list[tuple[str, float]]:
    """Top-k candidates by dot product, descending. `exclude` paths are skipped."""
    scored = [(path, dot(query, vec)) for path, vec in candidates if path not in exclude]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:k]
