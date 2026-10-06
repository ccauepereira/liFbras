import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from ml.retrieval_baseline import (
    CLASSES, aggregate_classes, angular, descriptor, distance, load_prepared,
    medoid_indices, motion, random_metrics, rank_instances, ranking_metrics,
    representation,
    run_experiment,
)


DATA = "dataset/libras-eqt-uece/mvp-hand-landmarks.npz"


def test_prepared_contract_and_resampling():
    data = load_prepared(DATA)
    assert data.label_names == CLASSES
    assert len(data.labels) == 150
    for sequence in data.sequences[:5]:
        x = representation(sequence, "raw")
        assert x.shape == (60, 126)
        assert np.isfinite(x).all()


def test_all_representations_finite_and_expected_shapes():
    data = load_prepared(DATA)
    expected = {"raw": 126, "wrist_scale": 126, "local_hand": 126, "angular": 30, "motion": 14}
    for name, width in expected.items():
        x = representation(data.sequences[0], name)
        assert x.shape == (60, width)
        assert np.isfinite(x).all()


def test_descriptor_families_are_small_and_deterministic():
    x = np.arange(60 * 4, dtype=np.float32).reshape(60, 4)
    assert np.array_equal(descriptor(x, "flat"), descriptor(x, "flat"))
    assert descriptor(x, "stats").shape == (16,)


def test_distance_and_tie_breaking():
    assert distance(np.zeros(2), np.zeros(2), "cosine") == 0
    assert distance(np.zeros(2), np.ones(2), "cosine") == 1
    ranked = rank_instances(np.zeros(1), [np.ones(1), np.ones(1)], np.array([1, 0]), np.array(["a", "b"]), np.array(["x", "y"]), "euclidean")
    assert [x["index"] for x in ranked] == [0, 1]


def test_class_aggregation_and_metrics():
    ranking = [{"label": 0, "distance": 2}, {"label": 1, "distance": 1}, {"label": 0, "distance": 3}]
    assert aggregate_classes(ranking, 1, "best")[0]["label"] == 1
    assert aggregate_classes(ranking, 3, "mean")[0]["label"] == 1
    assert ranking_metrics(ranking, 1) == {"r1": 0, "r3": 1, "mrr": 0.5}


def test_medoid_and_random_baseline():
    vectors = [np.array([0.0]), np.array([1.0]), np.array([10.0])]
    labels = np.array([0, 0, 1])
    assert medoid_indices(vectors, labels, "euclidean")[0] == 0
    baseline = random_metrics(100, 5, seed=203)
    assert baseline["chance_r1"] == pytest.approx(0.2)
    assert baseline["chance_r3"] == pytest.approx(0.6)


def test_lopo_gallery_excludes_query_signer():
    data = load_prepared(DATA)
    result = run_experiment(data, "motion", "stats", "euclidean")
    assert result["n_queries"] == 150
    for row in result["rows"]:
        assert all(item["signer"] != row["signer"] for item in row["top_instances"])
