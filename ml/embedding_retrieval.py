"""Small signer-held-out embedding retrieval experiment for LiFbras V2.05."""

from __future__ import annotations

import argparse
import copy
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

try:
    from .dtw_retrieval import representation_sequence
    from .retrieval_baseline import CLASSES, PreparedData, descriptor, load_prepared, distance
except ImportError:
    from dtw_retrieval import representation_sequence
    from retrieval_baseline import CLASSES, PreparedData, descriptor, load_prepared, distance


SEEDS = (42, 123, 2026)
DEVICE = torch.device("cpu")


def seed_everything(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)


def build_inputs(data: PreparedData) -> dict[str, np.ndarray]:
    stats = np.stack([descriptor(representation_sequence(s, "wrist_scale", True), "stats") for s in data.sequences])
    wrist = np.stack([representation_sequence(s, "wrist_scale", True) for s in data.sequences])
    local_motion = np.stack([representation_sequence(s, "local_global_motion", True) for s in data.sequences])
    return {"stats": stats.astype(np.float32), "wrist_scale": wrist.astype(np.float32), "local_global_motion": local_motion.astype(np.float32)}


class MLPEmbedding(nn.Module):
    def __init__(self, input_dim: int, embedding_dim: int = 64):
        super().__init__(); self.net = nn.Sequential(nn.Linear(input_dim, 128), nn.ReLU(), nn.Linear(128, embedding_dim))
    def forward(self, x): return F.normalize(self.net(x), dim=-1)


class GRUEmbedding(nn.Module):
    def __init__(self, input_dim: int, embedding_dim: int = 64):
        super().__init__(); self.gru = nn.GRU(input_dim, 64, batch_first=True); self.proj = nn.Linear(64, embedding_dim)
    def forward(self, x):
        _, h = self.gru(x); return F.normalize(self.proj(h[-1]), dim=-1)


class ConvEmbedding(nn.Module):
    def __init__(self, input_dim: int, embedding_dim: int = 64):
        super().__init__(); self.conv = nn.Sequential(nn.Conv1d(input_dim, 64, 5, padding=2), nn.ReLU(), nn.AdaptiveAvgPool1d(1)); self.proj = nn.Linear(64, embedding_dim)
    def forward(self, x): return F.normalize(self.proj(self.conv(x.transpose(1, 2)).squeeze(-1)), dim=-1)


def make_model(family: str, input_dim: int, embedding_dim: int) -> nn.Module:
    if family == "mlp": return MLPEmbedding(input_dim, embedding_dim)
    if family == "gru": return GRUEmbedding(input_dim, embedding_dim)
    if family == "conv1d": return ConvEmbedding(input_dim, embedding_dim)
    raise ValueError(f"unknown family: {family}")


def supervised_contrastive_loss(z: torch.Tensor, labels: torch.Tensor, signers: torch.Tensor, temperature: float = 0.1) -> torch.Tensor:
    logits = z @ z.T / temperature
    eye = torch.eye(len(z), dtype=torch.bool, device=z.device)
    logits = logits.masked_fill(eye, -1e9)
    positive = (labels[:, None] == labels[None, :]) & (signers[:, None] != signers[None, :]) & ~eye
    # If a tiny batch has no cross-signer positive, use same-class examples as
    # a safe fallback; the normal sampler always supplies the preferred case.
    positive = torch.where(positive.any(1, keepdim=True), positive, (labels[:, None] == labels[None, :]) & ~eye)
    log_prob = logits - torch.logsumexp(logits, dim=1, keepdim=True)
    counts = positive.sum(1).clamp_min(1)
    return -((log_prob * positive).sum(1) / counts).mean()


def triplet_loss(z: torch.Tensor, labels: torch.Tensor, signers: torch.Tensor, margin: float = 0.2) -> torch.Tensor:
    losses = []
    for i in range(len(z)):
        pos = torch.where((labels == labels[i]) & (signers != signers[i]))[0]
        neg = torch.where(labels != labels[i])[0]
        if len(pos) and len(neg):
            p = pos[0]; n = neg[torch.argmax(F.relu(margin + (z[i] @ z[p]) - z[i] @ z[neg].T))]
            losses.append(F.relu(margin + (z[i] @ z[p]) - (z[i] @ z[n])))
    return torch.stack(losses).mean() if losses else z.sum() * 0


def make_batches(indices: list[int], labels: np.ndarray, signers: np.ndarray, seed: int, batch_classes: int = 5) -> list[np.ndarray]:
    rng = np.random.default_rng(seed); by_class = {c: [i for i in indices if labels[i] == c] for c in range(len(CLASSES))}; batches = []
    for _ in range(max(1, len(indices) // (batch_classes * 2))):
        chosen = []
        for c in rng.choice(list(by_class), size=min(batch_classes, len(by_class)), replace=False):
            pool = by_class[c]; by_signer = {}
            for i in pool: by_signer.setdefault(str(signers[i]), []).append(i)
            groups = list(by_signer.values());
            if len(groups) >= 2: chosen.extend([rng.choice(groups[j]) for j in rng.choice(len(groups), 2, replace=False)])
            else: chosen.extend(rng.choice(pool, min(2, len(pool)), replace=False).tolist())
        batches.append(np.asarray(chosen, dtype=np.int64))
    return batches


def scaler_fit(x: np.ndarray, indices: list[int]) -> tuple[np.ndarray, np.ndarray]:
    mean = x[indices].mean(0); std = x[indices].std(0); return mean, np.where(std < 1e-6, 1.0, std)


def transform(x: np.ndarray, scaler: tuple[np.ndarray, np.ndarray], indices: list[int] | None = None) -> np.ndarray:
    mean, std = scaler; y = (x - mean) / std; return y if indices is None else y[indices]


def train_model(model: nn.Module, x: np.ndarray, labels: np.ndarray, signers: np.ndarray, train_idx: list[int], val_idx: list[int], family: str, loss_name: str, seed: int, max_epochs: int = 12) -> tuple[nn.Module, int, list[float]]:
    seed_everything(seed); optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4); best_state = copy.deepcopy(model.state_dict()); best_score, best_epoch, history = -1.0, 1, []
    for epoch in range(1, max_epochs + 1):
        model.train()
        for batch in make_batches(train_idx, labels, signers, seed + epoch):
            xb = torch.from_numpy(x[batch]).float(); z = model(xb); y = torch.from_numpy(labels[batch]).long(); s = torch.tensor([hash(str(signers[i])) % 100000 for i in batch], dtype=torch.long)
            loss = supervised_contrastive_loss(z, y, s) if loss_name == "supcon" else triplet_loss(z, y, s)
            optimizer.zero_grad(); loss.backward(); optimizer.step()
        score = validation_recall(model, x, labels, val_idx, train_idx); history.append(score)
        if score > best_score: best_score, best_epoch, best_state = score, epoch, copy.deepcopy(model.state_dict())
    model.load_state_dict(best_state); return model, best_epoch, history


def train_fixed(model: nn.Module, x: np.ndarray, labels: np.ndarray, signers: np.ndarray, train_idx: list[int], loss_name: str, seed: int, epochs: int) -> nn.Module:
    seed_everything(seed); optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    for epoch in range(1, max(1, epochs) + 1):
        model.train()
        for batch in make_batches(train_idx, labels, signers, seed + epoch):
            xb = torch.from_numpy(x[batch]).float(); z = model(xb); y = torch.from_numpy(labels[batch]).long(); s = torch.tensor([hash(str(signers[i])) % 100000 for i in batch], dtype=torch.long)
            loss = supervised_contrastive_loss(z, y, s) if loss_name == "supcon" else triplet_loss(z, y, s)
            optimizer.zero_grad(); loss.backward(); optimizer.step()
    return model


@torch.no_grad()
def embed(model: nn.Module, x: np.ndarray, indices: list[int]) -> np.ndarray:
    model.eval(); return model(torch.from_numpy(x[indices]).float()).cpu().numpy()


def rank_metrics(query: np.ndarray, gallery: np.ndarray, labels: np.ndarray, true: int) -> dict:
    d = 1.0 - query @ gallery.T
    class_scores = {int(c): float(np.min(d[labels == c])) for c in sorted(set(labels.tolist()))}
    order = sorted(class_scores, key=lambda c: (class_scores[c], c)); rank = order.index(true) + 1 if true in order else len(order) + 1
    d1 = class_scores[order[0]]; d2 = class_scores[order[1]] if len(order) > 1 else d1
    return {"r1": int(rank <= 1), "r3": int(rank <= 3), "mrr": 1.0 / rank, "rank": rank, "d1": d1, "d2": d2, "class_order": order}


def validation_recall(model: nn.Module, x: np.ndarray, labels: np.ndarray, query_idx: list[int], gallery_idx: list[int]) -> float:
    if not query_idx or not gallery_idx: return 0.0
    q, g = embed(model, x, query_idx), embed(model, x, gallery_idx); return float(np.mean([rank_metrics(q[i], g, labels[gallery_idx], int(labels[query_idx[i]]))["r1"] for i in range(len(query_idx))]))


def evaluate_fold(model: nn.Module, x: np.ndarray, data: PreparedData, test_idx: list[int], gallery_idx: list[int], representation: str, family: str, seed: int) -> dict:
    q, g = embed(model, x, test_idx), embed(model, x, gallery_idx); rows = []
    for i, qi in enumerate(test_idx):
        metrics = rank_metrics(q[i], g, data.labels[gallery_idx], int(data.labels[qi])); rows.append({"query": qi, "signer": str(data.signers[qi]), "class": int(data.labels[qi]), "metrics": metrics, "top": metrics["class_order"][:3], "d1": metrics["d1"], "d2": metrics["d2"], "margin": metrics["d2"] - metrics["d1"], "ratio": metrics["d1"] / metrics["d2"] if metrics["d2"] else 0.0})
    return {"representation": representation, "family": family, "seed": seed, "rows": rows, "summary": summarize(rows)}


def summarize(rows: list[dict]) -> dict:
    def avg(rs): return {k: float(np.mean([r["metrics"][k] for r in rs])) for k in ("r1", "r3", "mrr")}
    return {"overall": avg(rows), "per_signer": {str(s): avg([r for r in rows if r["signer"] == s]) for s in sorted({r["signer"] for r in rows})}, "per_class": {str(c): avg([r for r in rows if r["class"] == c]) for c in sorted({r["class"] for r in rows})}}


def parameter_count(model: nn.Module) -> int: return sum(p.numel() for p in model.parameters())


def run_config(data: PreparedData, inputs: dict[str, np.ndarray], family: str, representation: str, loss_name: str, seeds: tuple[int, ...] = SEEDS) -> dict:
    x = inputs[representation]; all_rows = []; fold_rows = []; quality = []; prototype_rows = []; medoid_rows = []; latency_samples = []
    for test_signer in sorted(set(data.signers.tolist())):
        test_idx = [i for i, s in enumerate(data.signers) if s == test_signer]; dev = [i for i, s in enumerate(data.signers) if s != test_signer]; val_signer = sorted(set(data.signers[dev].tolist()))[-1]; inner_train = [i for i in dev if data.signers[i] != val_signer]; val_idx = [i for i in dev if data.signers[i] == val_signer]
        scaler = scaler_fit(x, inner_train) if family == "mlp" else (np.zeros(x.shape[1:], dtype=np.float32), np.ones(x.shape[1:], dtype=np.float32))
        sx = transform(x, scaler)
        for seed in seeds:
            seed_everything(seed); model = make_model(family, sx.shape[-1], 64).to(DEVICE); model, epochs, _ = train_model(model, sx, data.labels, data.signers, inner_train, val_idx, family, loss_name, seed)
            # Freeze hyperparameters/epoch count, then refit on all four development signers.
            seed_everything(seed); final = make_model(family, sx.shape[-1], 64).to(DEVICE); final = train_fixed(final, sx, data.labels, data.signers, dev, loss_name, seed, epochs)
            if family == "mlp" and loss_name == "supcon" and seed == 42:
                ckpt = Path("ml/results/v205-checkpoints"); ckpt.mkdir(parents=True, exist_ok=True)
                torch.save({"state_dict": final.state_dict(), "mean": scaler[0], "std": scaler[1], "test_signer": str(test_signer), "representation": representation, "embedding_dim": 64}, ckpt / f"mlp-{str(test_signer).replace(' ', '_')}.pt")
            result = evaluate_fold(final, sx, data, test_idx, dev, representation, family, seed); result["test_signer"] = test_signer; result["epochs"] = epochs; result["parameters"] = parameter_count(final); all_rows.extend(result["rows"]); fold_rows.append(result)
            zdev, ztest = embed(final, sx, dev), embed(final, sx, test_idx); labels_dev = data.labels[dev]
            same, different, same_s, different_s = [], [], [], []
            for a in range(len(dev)):
                for b in range(a + 1, len(dev)):
                    d = float(1.0 - zdev[a] @ zdev[b]);
                    (same if labels_dev[a] == labels_dev[b] else different).append(d)
                    (same_s if data.signers[dev[a]] == data.signers[dev[b]] else different_s).append(d)
            quality.append({"intra_class": float(np.mean(same)), "inter_class": float(np.mean(different)), "intra_signer": float(np.mean(same_s)), "inter_signer": float(np.mean(different_s))})
            centroids = np.stack([zdev[labels_dev == c].mean(0) for c in range(len(CLASSES))]); centroids /= np.linalg.norm(centroids, axis=1, keepdims=True).clip(min=1e-8)
            medoids = []
            for c in range(len(CLASSES)):
                ids = np.where(labels_dev == c)[0]; scores = [np.mean(1.0 - zdev[j] @ zdev[ids].T) for j in ids]; medoids.append(zdev[ids[int(np.argmin(scores))]])
            medoids = np.stack(medoids)
            for i, qi in enumerate(test_idx):
                order = np.argsort(1.0 - ztest[i] @ centroids.T); rank = int(np.where(order == data.labels[qi])[0][0] + 1); prototype_rows.append({"signer": str(data.signers[qi]), "class": int(data.labels[qi]), "r1": int(rank == 1), "r3": int(rank <= 3), "mrr": 1.0 / rank})
                order = np.argsort(1.0 - ztest[i] @ medoids.T); rank = int(np.where(order == data.labels[qi])[0][0] + 1); medoid_rows.append({"signer": str(data.signers[qi]), "class": int(data.labels[qi]), "metrics": {"r1": int(rank == 1), "r3": int(rank <= 3), "mrr": 1.0 / rank}})
            t = time.perf_counter(); _ = embed(final, sx, [test_idx[0]]); latency_samples.append(("forward", (time.perf_counter() - t) * 1000)); qv = ztest[0]; t = time.perf_counter(); _ = 1.0 - qv @ zdev.T; latency_samples.append(("distance", (time.perf_counter() - t) * 1000)); t = time.perf_counter(); np.argsort(1.0 - qv @ zdev.T); latency_samples.append(("ranking", (time.perf_counter() - t) * 1000))
    seed_summaries = {str(seed): summarize([r for r in all_rows if any(f["seed"] == seed and r in f["rows"] for f in fold_rows)]) for seed in seeds}
    qmeans = {k: float(np.mean([q[k] for q in quality])) for k in quality[0]}; ratio = qmeans["intra_class"] / qmeans["inter_class"]
    return {"family": family, "representation": representation, "loss": loss_name, "seeds": list(seeds), "summary": summarize(all_rows), "seed_summaries": seed_summaries, "folds": fold_rows, "parameters": max(r["parameters"] for r in fold_rows), "checkpoint_bytes": max(r["parameters"] for r in fold_rows) * 4, "embedding_bytes": 64 * 4, "quality": {**qmeans, "class_ratio": ratio, "signer_ratio": qmeans["intra_signer"] / qmeans["inter_signer"]}, "prototype": summarize([{"signer": r["signer"], "class": r["class"], "metrics": {"r1": r["r1"], "r3": r["r3"], "mrr": r["mrr"]}} for r in prototype_rows]), "medoid": summarize(medoid_rows), "latency_ms": {name: {"median": float(np.median([v for n, v in latency_samples if n == name])), "p95": float(np.percentile([v for n, v in latency_samples if n == name], 95))} for name in ("forward", "distance", "ranking")}}


def linear_baseline(data: PreparedData, inputs: dict[str, np.ndarray]) -> dict:
    x = inputs["stats"]; rows = []
    for test_signer in sorted(set(data.signers.tolist())):
        test = [i for i, s in enumerate(data.signers) if s == test_signer]; gallery = [i for i, s in enumerate(data.signers) if s != test_signer]; scaler = scaler_fit(x, gallery); z = transform(x, scaler); rows.extend({"query": i, "signer": str(data.signers[i]), "class": int(data.labels[i]), "metrics": rank_metrics(z[i] / np.linalg.norm(z[i]), z[gallery] / np.linalg.norm(z[gallery], axis=1, keepdims=True), data.labels[gallery], int(data.labels[i]))} for i in test)
    return {"family": "linear", "representation": "stats", "summary": summarize(rows), "parameters": 0, "rows": rows}


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--data", default="dataset/libras-eqt-uece/mvp-hand-landmarks.npz"); p.add_argument("--output", default="ml/results/v205-embedding-retrieval.json"); args = p.parse_args()
    data = load_prepared(args.data); inputs = build_inputs(data); results = [linear_baseline(data, inputs)]
    # Three small families; contrastive MLP/GRU receive the three-seed final run.
    configs = [("mlp", "stats", "supcon", SEEDS), ("mlp", "stats", "triplet", (SEEDS[0],)), ("gru", "wrist_scale", "supcon", SEEDS), ("conv1d", "wrist_scale", "supcon", (SEEDS[0],))]
    for family, rep, loss, seeds in configs:
        print("training", family, flush=True); results.append(run_config(data, inputs, family, rep, loss, seeds))
    out = {"contract": {"sequences": len(data.labels), "frames": int(sum(map(len, data.sequences))), "classes": list(data.label_names), "signers": sorted(set(data.signers.tolist())), "values_per_frame": 126}, "results": results, "random": {"r1": .2, "r3": .6, "mrr": .4566666667}}
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"); print(path)


if __name__ == "__main__": main()
