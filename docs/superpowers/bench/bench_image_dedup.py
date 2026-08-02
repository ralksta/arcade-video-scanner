"""Benchmark + recall check: BK-tree vs 4-char prefix bucketing vs brute force.

Candidate search for near-duplicate perceptual hashes. Measures both runtime
and — more importantly — how many true near-duplicate pairs each strategy
actually finds, using brute force as ground truth.

Run: .venv/bin/python3.13 docs/superpowers/bench/bench_image_dedup.py
(needs the interpreter that has imagehash installed)
"""
import random
import statistics
import time
from collections import defaultdict

import imagehash

THRESHOLD = 5
REPEATS = 5


def make_hashes(n, rng):
    """n hashes: clustered near-duplicates plus unrelated noise."""
    hashes = []
    n_clusters = n // 8
    for _ in range(n_clusters):
        base = rng.getrandbits(64)
        hashes.append(base)
        for _ in range(rng.randint(1, 3)):
            variant = base
            for _ in range(rng.randint(1, THRESHOLD)):
                variant ^= 1 << rng.randrange(64)
            hashes.append(variant)
    while len(hashes) < n:
        hashes.append(rng.getrandbits(64))
    rng.shuffle(hashes)
    return [(f"{h:016x}", imagehash.hex_to_hash(f"{h:016x}")) for h in hashes[:n]]


def brute_force_pairs(data, threshold):
    pairs = set()
    for i in range(len(data)):
        for j in range(i + 1, len(data)):
            if data[i][1] - data[j][1] <= threshold:
                pairs.add((i, j))
    return pairs


def prefix_pairs(data, threshold):
    """Old implementation: bucket by first 4 hex chars, compare within bucket."""
    buckets = defaultdict(list)
    for idx, (hash_str, _) in enumerate(data):
        buckets[hash_str[:4]].append(idx)

    pairs = set()
    for indices in buckets.values():
        if len(indices) < 2:
            continue
        for pos, i in enumerate(indices):
            for j in indices[pos + 1:]:
                if data[i][1] - data[j][1] <= threshold:
                    pairs.add((min(i, j), max(i, j)))
    return pairs


def banded_pairs(data, threshold):
    """New implementation: banded candidate index + exact distance check."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    from arcade_scanner.core.duplicate_detector import _BandedHashIndex, _hamming

    index = _BandedHashIndex(bits=len(data[0][0]) * 4, threshold=threshold)
    values = []
    for idx, (hash_str, _) in enumerate(data):
        value = int(hash_str, 16)
        values.append(value)
        index.add(idx, value)

    pairs = set()
    for i, (_, phash) in enumerate(data):
        for j in index.candidates(values[i]):
            if i != j and _hamming(values[i], values[j]) <= threshold:
                pairs.add((min(i, j), max(i, j)))
    return pairs


def timed(fn, data, threshold):
    times = []
    for _ in range(REPEATS):
        t0 = time.perf_counter()
        result = fn(data, threshold)
        times.append(time.perf_counter() - t0)
    return statistics.median(times), result


def main():
    rng = random.Random(20260802)
    print(f"threshold = {THRESHOLD} bits, median of {REPEATS} runs\n")
    header = f"{'n':>7} {'brute':>10} {'prefix':>10} {'banded':>10}   {'prefix recall':>14} {'banded recall':>14}"
    print(header)
    print("-" * len(header))

    for n in (500, 2000, 5000):
        data = make_hashes(n, rng)

        t_brute, truth = timed(brute_force_pairs, data, THRESHOLD)
        t_prefix, found_prefix = timed(prefix_pairs, data, THRESHOLD)
        t_bk, found_bk = timed(banded_pairs, data, THRESHOLD)

        rec_prefix = len(found_prefix & truth) / len(truth) if truth else 1.0
        rec_bk = len(found_bk & truth) / len(truth) if truth else 1.0

        print(
            f"{n:>7} {t_brute*1000:>9.1f}ms {t_prefix*1000:>9.1f}ms {t_bk*1000:>9.1f}ms"
            f"   {rec_prefix*100:>13.1f}% {rec_bk*100:>13.1f}%"
        )
        assert found_bk == truth, "banded index must be exact"

    print("\nrecall = share of true near-duplicate pairs found (brute force = ground truth)")


if __name__ == "__main__":
    main()
