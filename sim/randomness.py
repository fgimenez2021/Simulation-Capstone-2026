from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .types import DistSpec


@dataclass


class RNG:
    """
    Simple wrapper around NumPy Generator for reproducibility.
    """
    seed: int
    gen: np.random.Generator

    @classmethod
    def from_seed(cls, seed: int) -> "RNG":
        return cls(seed=seed, gen=np.random.default_rng(seed))


def sample_dist(spec: DistSpec, rng: RNG) -> float:
    """
    Sample a non-negative float from a distribution specification.

    Supported:
      - fixed:      params {value}
      - triangular: params {low, mode, high}
      - lognormal:  params {mean, sigma}

    Returns:
      float >= 0.0
    """
    dist = spec.dist
    p = spec.params

    if dist == "fixed":
        value = float(p.get("value", 0.0))
        return max(0.0, value)

    if dist == "triangular":
        low = float(p["low"])
        mode = float(p["mode"])
        high = float(p["high"])
        if not (low <= mode <= high):
            raise ValueError(f"Triangular params must satisfy low <= mode <= high. Got: {p}")
        value = float(rng.gen.triangular(left=low, mode=mode, right=high))
        return max(0.0, value)

    if dist == "lognormal":
        mean = float(p["mean"])
        sigma = float(p["sigma"])
        if sigma < 0:
            raise ValueError(f"Lognormal sigma must be >= 0. Got: {sigma}")
        value = float(rng.gen.lognormal(mean=mean, sigma=sigma))
        return max(0.0, value)

    raise ValueError(f"Unsupported distribution: {dist}")


def bernoulli(p: float, rng: RNG) -> bool:
    """
    Return True with probability p.
    """
    if p <= 0:
        return False
    if p >= 1:
        return True
    return bool(rng.gen.random() < p)
