import sys
from pathlib import Path

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[2]))

from ml.embedding_retrieval import (
    CLASSES, MLPEmbedding, make_batches, make_model, parameter_count,
    rank_metrics, scaler_fit, supervised_contrastive_loss,
)


def test_embedding_shape_finite_and_l2_normalized():
    model = MLPEmbedding(8, 32)
    z = model(torch.randn(3, 8))
    assert z.shape == (3, 32)
    assert torch.isfinite(z).all()
    assert torch.linalg.norm(z, dim=1).detach().numpy() == pytest.approx(np.ones(3))


def test_sampler_prefers_cross_signer_same_class():
    labels = np.repeat(np.arange(5), 2)
    signers = np.tile(np.array(["S1", "S2"]), 5)
    batches = make_batches(list(range(10)), labels, signers, 42)
    assert batches
    for batch in batches:
        for c in range(5):
            ids = [i for i in batch if labels[i] == c]
            assert len(ids) == 2
            assert signers[ids[0]] != signers[ids[1]]


def test_contrastive_positive_mask_is_cross_signer():
    z = torch.tensor([[1., 0.], [1., 0.], [0., 1.]])
    labels = torch.tensor([0, 0, 1]); signers = torch.tensor([1, 2, 1])
    loss = supervised_contrastive_loss(z, labels, signers)
    assert torch.isfinite(loss)
    assert loss.item() < 1.0


def test_scaler_uses_only_train_indices():
    x = np.array([[0.], [2.], [100.]])
    mean, std = scaler_fit(x, [0, 1])
    assert mean == pytest.approx([1.])
    assert std == pytest.approx([1.])


def test_ranking_recall_and_mrr_and_checkpoint(tmp_path):
    q = np.array([1., 0.]); g = np.array([[1., 0.], [0., 1.]])
    metrics = rank_metrics(q, g, np.array([0, 1]), 0)
    assert metrics["r1"] == 1 and metrics["r3"] == 1 and metrics["mrr"] == 1
    model = make_model("mlp", 4, 32)
    path = tmp_path / "checkpoint.pt"
    torch.save(model.state_dict(), path)
    restored = make_model("mlp", 4, 32); restored.load_state_dict(torch.load(path, weights_only=True))
    assert parameter_count(restored) < 500_000
