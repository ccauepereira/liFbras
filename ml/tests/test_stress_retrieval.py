import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from ml.stress_retrieval import (
    contiguous_gap, gaussian_noise, hand_dropout, mirror, padding, perturbation,
    random_drop, rotate_xy, scale, speed, translate,
)


def sample():
    x = np.zeros((20, 126), dtype=np.float32); x[:, :63] = .3; x[:, 63:] = .7; return x


def test_temporal_perturbations_preserve_shape_contract_and_order():
    x = sample(); assert speed(x, .6).shape[0] == 12; assert len(random_drop(x, .2, 42)) <= 20
    assert len(contiguous_gap(x, .1, "middle")) == 18
    assert len(padding(x, .1, "both")) == 24


def test_hand_dropout_uses_zero_absence_convention():
    y = hand_dropout(sample(), .2, 1)
    assert np.all(y[8:12, 63:] == 0)
    assert np.all(y[8:12, :63] != 0)


def test_geometric_perturbations_finite_and_mirror_modes_differ():
    x = sample();
    for y in (gaussian_noise(x, .005, 42), translate(x, .02, 0), scale(x, .9), mirror(x), mirror(x, True), rotate_xy(x, 5), perturbation("realistic_stress", x)):
        assert y.shape[1] == x.shape[1] and np.isfinite(y).all()
    assert not np.array_equal(mirror(x), mirror(x, True))


def test_random_reproducibility_and_label_independence():
    np.testing.assert_array_equal(random_drop(sample(), .2, 42), random_drop(sample(), .2, 42))
    assert perturbation("clean", sample()).shape == (20, 126)


def test_invalid_noise_is_not_silently_accepted():
    with pytest.raises(ValueError):
        gaussian_noise(np.full((2, 126), np.nan, dtype=np.float32), .1, 1)
