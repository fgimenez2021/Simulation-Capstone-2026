"""Tests for the RNG wrapper and distribution sampling."""

import pytest

from sim.randomness import RNG, bernoulli, sample_dist
from sim.types import DistSpec


def test_rng_deterministic():
    a = RNG.from_seed(42)
    b = RNG.from_seed(42)
    vals_a = [float(a.gen.random()) for _ in range(10)]
    vals_b = [float(b.gen.random()) for _ in range(10)]
    assert vals_a == vals_b


def test_rng_different_seeds_differ():
    a = RNG.from_seed(1)
    b = RNG.from_seed(2)
    assert float(a.gen.random()) != float(b.gen.random())


def test_sample_fixed():
    rng = RNG.from_seed(0)
    spec = DistSpec(dist="fixed", params={"value": 3.5})
    assert sample_dist(spec, rng) == 3.5


def test_sample_fixed_negative_clamped():
    rng = RNG.from_seed(0)
    spec = DistSpec(dist="fixed", params={"value": -1.0})
    assert sample_dist(spec, rng) == 0.0


def test_sample_triangular_in_range():
    rng = RNG.from_seed(99)
    spec = DistSpec(dist="triangular", params={"low": 1.0, "mode": 5.0, "high": 10.0})
    for _ in range(100):
        v = sample_dist(spec, rng)
        assert 1.0 <= v <= 10.0


def test_sample_triangular_bad_params():
    rng = RNG.from_seed(0)
    spec = DistSpec(dist="triangular", params={"low": 10.0, "mode": 1.0, "high": 5.0})
    with pytest.raises(ValueError, match="low <= mode <= high"):
        sample_dist(spec, rng)


def test_sample_lognormal_positive():
    rng = RNG.from_seed(7)
    spec = DistSpec(dist="lognormal", params={"mean": 0.0, "sigma": 0.5})
    for _ in range(50):
        assert sample_dist(spec, rng) > 0.0


def test_sample_unsupported_dist():
    rng = RNG.from_seed(0)
    spec = DistSpec(dist="uniform", params={"low": 0, "high": 1})
    with pytest.raises(ValueError, match="Unsupported distribution"):
        sample_dist(spec, rng)


def test_bernoulli_always_true():
    rng = RNG.from_seed(0)
    assert all(bernoulli(1.0, rng) for _ in range(20))


def test_bernoulli_always_false():
    rng = RNG.from_seed(0)
    assert not any(bernoulli(0.0, rng) for _ in range(20))


def test_bernoulli_probabilistic():
    rng = RNG.from_seed(42)
    results = [bernoulli(0.5, rng) for _ in range(1000)]
    rate = sum(results) / len(results)
    assert 0.4 < rate < 0.6
