"""Stable independent random streams for controlled generation."""

from __future__ import annotations

import hashlib
import random


SUBSEED_NAMES = (
    "population",
    "hierarchy",
    "dependencies",
    "duration",
    "temporal",
    "priority",
    "anchors",
    "lifecycle",
    "expired-anchor-history",
    "actionable-parents",
    "heterogeneity",
)


def derive_subseed(seed: int, namespace: str) -> int:
    """Derive a stable integer seed without Python's randomized hash()."""
    if namespace not in SUBSEED_NAMES:
        raise ValueError(f"unknown generator RNG namespace: {namespace}")

    payload = f"arc-generator-v1:{seed}:{namespace}".encode()
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def rng_for(seed: int, namespace: str) -> random.Random:
    """Return an isolated deterministic RNG stream for one concern."""
    return random.Random(derive_subseed(seed, namespace))
