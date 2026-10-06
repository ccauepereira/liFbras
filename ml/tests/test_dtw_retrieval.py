import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from ml.dtw_retrieval import dtw_distance, evaluate
from ml.retrieval_baseline import CLASSES, PreparedData, load_prepared


def test_identical_sequences_zero_and_valid_path():
    x = np.arange(12, dtype=np.float32).reshape(6, 2)
    result = dtw_distance(x, x, "euclidean", normalize=False)
    assert result["distance"] == pytest.approx(0)
    assert result["path_length"] >= 6
    assert result["path"][0] == (0, 0)
    assert result["path"][-1] == (5, 5)


def test_symmetry_and_different_lengths():
    x = np.zeros((3, 2), dtype=np.float32)
    y = np.ones((7, 2), dtype=np.float32)
    a = dtw_distance(x, y, "manhattan")
    b = dtw_distance(y, x, "manhattan")
    assert a["raw_distance"] == pytest.approx(b["raw_distance"])
    assert a["path_length"] == b["path_length"]
    assert np.isfinite(a["distance"])


def test_normalization_and_band():
    x = np.zeros((5, 1), dtype=np.float32)
    y = np.ones((5, 1), dtype=np.float32)
    raw = dtw_distance(x, y, normalize=False)
    normalized = dtw_distance(x, y, normalize=True)
    assert normalized["distance"] == pytest.approx(raw["raw_distance"] / raw["path_length"])
    assert dtw_distance(x, y, band_fraction=0.2)["path_length"] > 0


def test_rejects_nonfinite():
    with pytest.raises(ValueError):
        dtw_distance(np.array([[np.nan]]), np.zeros((1, 1)))


def test_lopo_evaluation_has_no_same_signer_gallery():
    sequences = tuple(np.full((4 + i, 126), i / 10, dtype=np.float32) for i in range(10))
    data = PreparedData(sequences, np.arange(10) % 5, CLASSES,
                        np.array([f"S{i % 2}" for i in range(10)]), np.array([f"f{i}" for i in range(10)]))
    result = evaluate(data, "motion", "euclidean", True, 0.2)
    assert result["n_queries"] == 10
    for row in result["rows"]:
        assert all(x["signer"] != row["signer"] for x in row["top_instances"])
