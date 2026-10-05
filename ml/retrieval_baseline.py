"""Offline geometric retrieval baselines for LiFbras V2.03.

The module deliberately has no ML framework dependency.  It consumes the
prepared five-class NPZ, evaluates leave-one-signer-out (LOPO) retrieval, and
exposes small pure functions used by tests and the report.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    from .preprocessamento import reamostrar_temporal, preprocessar_sequencia
except ImportError:  # executed as ``python ml/retrieval_baseline.py``
    from preprocessamento import reamostrar_temporal, preprocessar_sequencia


CLASSES = ("2_Sim", "7_Quero", "92_Energia", "110_Menos", "111_Mais")
T = 60
D = 126
LANDMARKS = 21
HAND = 63
FINGERS = ((0, 1, 2, 3, 4), (0, 5, 6, 7, 8), (0, 9, 10, 11, 12),
           (0, 13, 14, 15, 16), (0, 17, 18, 19, 20))


@dataclass(frozen=True)
class PreparedData:
    sequences: tuple[np.ndarray, ...]
    labels: np.ndarray
    label_names: tuple[str, ...]
    signers: np.ndarray
    source_files: np.ndarray


def load_prepared(path: str | Path) -> PreparedData:
    """Load and validate the prepared archive contract."""
    with np.load(path, allow_pickle=False) as z:
        features = np.asarray(z["features"], dtype=np.float32)
        offsets = np.asarray(z["offsets"], dtype=np.int64)
        labels = np.asarray(z["label_ids"], dtype=np.int64)
        names = tuple(str(x) for x in z["label_names"].tolist())
        signers = np.asarray(z["signers"]).astype(str)
        source = np.asarray(z["source_files"]).astype(str)
    if names != CLASSES:
        raise ValueError(f"class order diverged: {names}")
    if features.ndim != 2 or features.shape[1] != D or not np.isfinite(features).all():
        raise ValueError(f"features must be finite [frames, {D}], got {features.shape}")
    if len(offsets) != len(labels) + 1 or offsets[0] != 0 or offsets[-1] != len(features):
        raise ValueError("invalid sequence offsets")
    if np.any(np.diff(offsets) < 1) or len(signers) != len(labels) or len(source) != len(labels):
        raise ValueError("invalid sequence metadata")
    sequences = tuple(features[offsets[i]: offsets[i + 1]].copy() for i in range(len(labels)))
    if np.any(labels < 0) or np.any(labels >= len(names)):
        raise ValueError("label id outside class list")
    return PreparedData(sequences, labels, names, signers, source)


def _hands(sequence: np.ndarray) -> np.ndarray:
    a = np.asarray(sequence, dtype=np.float32)
    if a.ndim != 2 or a.shape[1] != D:
        raise ValueError(f"expected [frames, {D}], got {a.shape}")
    return a.reshape(a.shape[0], 2, LANDMARKS, 3)


def local_hand(sequence: np.ndarray) -> np.ndarray:
    """Keep global wrist trajectories and express other landmarks per wrist."""
    out = _hands(sequence).copy()
    present = np.any(out != 0, axis=(2, 3))
    out[:, :, 1:] -= out[:, :, :1]
    out[~present] = 0.0
    return out.reshape(len(out), D)


def angular(sequence: np.ndarray) -> np.ndarray:
    """Return 15 inter-bone angles per hand (30 values per frame)."""
    h = _hands(sequence)
    result = np.zeros((len(h), 2, 15), dtype=np.float32)
    for hand in range(2):
        for finger_i, finger in enumerate(FINGERS):
            for j in range(1, len(finger) - 1):
                a = h[:, hand, finger[j]] - h[:, hand, finger[j - 1]]
                b = h[:, hand, finger[j + 1]] - h[:, hand, finger[j]]
                na = np.linalg.norm(a, axis=1)
                nb = np.linalg.norm(b, axis=1)
                valid = (na > 1e-7) & (nb > 1e-7)
                cosine = np.zeros(len(h), dtype=np.float32)
                cosine[valid] = np.sum(a[valid] * b[valid], axis=1) / (na[valid] * nb[valid])
                result[:, hand, finger_i * 3 + j - 1] = np.arccos(np.clip(cosine, -1, 1))
    return result.reshape(len(h), 30)


def motion(sequence: np.ndarray) -> np.ndarray:
    """Frame-space wrist and landmark motion descriptor (14 values/frame)."""
    h = _hands(sequence)
    wrists = h[:, :, 0]
    dw = np.diff(wrists, axis=0, prepend=wrists[:1])
    speed = np.linalg.norm(dw, axis=2)
    inter = wrists[:, 1] - wrists[:, 0]
    di = np.diff(inter, axis=0, prepend=inter[:1])
    landmark_delta = np.diff(h, axis=0, prepend=h[:1])
    mean_landmark = np.linalg.norm(landmark_delta, axis=3).mean(axis=2)
    inter_speed = np.linalg.norm(di, axis=1, keepdims=True)
    return np.concatenate((dw.reshape(len(h), 6), speed, inter, inter_speed, mean_landmark), axis=1).astype(np.float32)


def representation(sequence: np.ndarray, variant: str) -> np.ndarray:
    """Create one deterministic [T, F] representation."""
    sampled = reamostrar_temporal(sequence, tamanho=T, dimensao=D)
    if variant == "raw":
        out = sampled
    elif variant == "wrist_scale":
        out = preprocessar_sequencia(sequence, "wrist_scale", tamanho=T)
    elif variant == "local_hand":
        out = local_hand(sampled)
    elif variant == "angular":
        out = angular(sampled)
    elif variant == "motion":
        out = motion(sampled)
    else:
        raise ValueError(f"unknown representation: {variant}")
    if out.shape[0] != T or not np.isfinite(out).all():
        raise ValueError("representation is not finite or has wrong temporal size")
    return out.astype(np.float32, copy=False)


def descriptor(sequence_representation: np.ndarray, family: str) -> np.ndarray:
    """Flattened sequence or compact mean/std/displacement/delta descriptor."""
    x = np.asarray(sequence_representation, dtype=np.float32)
    if x.ndim != 2 or not np.isfinite(x).all():
        raise ValueError("descriptor input must be finite [T, F]")
    if family == "flat":
        return x.reshape(-1).astype(np.float64)
    if family == "stats":
        delta = np.diff(x, axis=0, prepend=x[:1])
        return np.concatenate((x.mean(0), x.std(0), x[-1] - x[0], np.abs(delta).mean(0))).astype(np.float64)
    raise ValueError(f"unknown descriptor family: {family}")


def distance(a: np.ndarray, b: np.ndarray, metric: str) -> float:
    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    if metric == "euclidean":
        return float(np.linalg.norm(d))
    if metric == "manhattan":
        return float(np.abs(d).sum())
    if metric == "cosine":
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 and nb == 0:
            return 0.0
        if na == 0 or nb == 0:
            return 1.0
        return float(1.0 - np.dot(a, b) / (na * nb))
    raise ValueError(f"unknown metric: {metric}")


def rank_instances(query: np.ndarray, gallery: list[np.ndarray], labels: np.ndarray, signers: np.ndarray,
                   source_files: np.ndarray, metric: str) -> list[dict]:
    ranked = []
    for i, item in enumerate(gallery):
        ranked.append({"index": i, "label": int(labels[i]), "signer": str(signers[i]),
                       "source_file": str(source_files[i]), "distance": distance(query, item, metric)})
    return sorted(ranked, key=lambda r: (r["distance"], r["index"]))


def aggregate_classes(ranking: list[dict], k: int = 1, mode: str = "best") -> list[dict]:
    by = defaultdict(list)
    for row in ranking:
        by[row["label"]].append(row["distance"])
    scored = []
    for label, values in by.items():
        vals = values[:k]
        scored.append({"label": label, "score": min(vals) if mode == "best" else float(np.mean(vals))})
    return sorted(scored, key=lambda r: (r["score"], r["label"]))


def medoid_indices(vectors: list[np.ndarray], labels: np.ndarray, metric: str) -> dict[int, int]:
    result = {}
    for label in sorted(set(int(x) for x in labels)):
        ids = [i for i, x in enumerate(labels) if int(x) == label]
        if len(ids) == 1:
            result[label] = ids[0]
            continue
        scores = [sum(distance(vectors[i], vectors[j], metric) for j in ids) / len(ids) for i in ids]
        result[label] = ids[int(np.argmin(scores))]
    return result


def ranking_metrics(ranking: list[dict], true_label: int) -> dict:
    labels = [x["label"] for x in ranking]
    rank = labels.index(true_label) + 1 if true_label in labels else len(labels) + 1
    return {"r1": int(rank <= 1), "r3": int(rank <= 3), "mrr": 1.0 / rank}


def random_metrics(n_queries: int, n_classes: int, seed: int = 203) -> dict:
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n_queries):
        rank = int(rng.integers(1, n_classes + 1))
        values.append((rank <= 1, rank <= 3, 1.0 / rank))
    return {"r1": float(np.mean([x[0] for x in values])), "r3": float(np.mean([x[1] for x in values])),
            "mrr": float(np.mean([x[2] for x in values])), "seed": seed,
            "chance_r1": 1.0 / n_classes, "chance_r3": min(3, n_classes) / n_classes}


def run_experiment(data: PreparedData, representation_name: str = "raw", family: str = "flat",
                   metric: str = "euclidean") -> dict:
    vectors = [descriptor(representation(x, representation_name), family) for x in data.sequences]
    signers = sorted(set(data.signers.tolist()))
    rows = []
    medoid_rows = []
    for held in signers:
        query_ids = [i for i, s in enumerate(data.signers) if s == held]
        gallery_ids = [i for i, s in enumerate(data.signers) if s != held]
        gallery = [vectors[i] for i in gallery_ids]
        medoids = medoid_indices(gallery, data.labels[gallery_ids], metric)
        medoid_gallery = [gallery[i] for i in medoids.values()]
        medoid_labels = np.asarray(list(medoids.keys()), dtype=np.int64)
        medoid_signers = np.asarray([data.signers[gallery_ids[i]] for i in medoids.values()])
        medoid_sources = np.asarray([data.source_files[gallery_ids[i]] for i in medoids.values()])
        for qi in query_ids:
            ranking = rank_instances(vectors[qi], gallery, data.labels[gallery_ids], data.signers[gallery_ids], data.source_files[gallery_ids], metric)
            # map ranking indexes to global ids for traceability
            for r in ranking:
                r["index"] = gallery_ids[r["index"]]
            for mode in ("best", "mean"):
                for k in (1, 3):
                    class_rank = aggregate_classes(ranking, k=k, mode=mode)
                    rows.append({"query": qi, "signer": held, "class": int(data.labels[qi]), "mode": mode, "k": k,
                                 "metrics": ranking_metrics(class_rank, int(data.labels[qi])),
                                 "top_classes": [x["label"] for x in class_rank[:3]], "top_instances": ranking[:3]})
            medoid_rank = rank_instances(vectors[qi], medoid_gallery, medoid_labels, medoid_signers, medoid_sources, metric)
            medoid_rows.append({"query": qi, "signer": held, "class": int(data.labels[qi]),
                                "metrics": ranking_metrics(medoid_rank, int(data.labels[qi]))})
    summary = {}
    for mode in ("best", "mean"):
        for k in (1, 3):
            selected = [r for r in rows if r["mode"] == mode and r["k"] == k]
            summary[f"{mode}_k{k}"] = _summarize(selected)
    summary["medoid"] = _summarize(medoid_rows)
    return {"representation": representation_name, "family": family, "metric": metric, "n_queries": len(medoid_rows),
            "summary": summary, "rows": rows, "medoid_rows": medoid_rows}


def _summarize(rows: list[dict]) -> dict:
    def avg(items):
        return {k: float(np.mean([x["metrics"][k] for x in items])) for k in ("r1", "r3", "mrr")}
    out = {"overall": avg(rows)}
    out["per_class"] = {str(c): avg([x for x in rows if x["class"] == c]) for c in sorted(set(x["class"] for x in rows))}
    out["per_signer"] = {str(s): avg([x for x in rows if x["signer"] == s]) for s in sorted(set(x["signer"] for x in rows))}
    return out


def dataset_table(data: PreparedData) -> list[dict]:
    rows = []
    for c, name in enumerate(data.label_names):
        for signer in sorted(set(data.signers.tolist())):
            lengths = [len(data.sequences[i]) for i in range(len(data.labels)) if int(data.labels[i]) == c and data.signers[i] == signer]
            if lengths:
                rows.append({"class": name, "signer": signer, "sequences": len(lengths), "min": min(lengths),
                             "mean": float(np.mean(lengths)), "median": float(np.median(lengths)), "max": max(lengths)})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="dataset/libras-eqt-uece/mvp-hand-landmarks.npz")
    parser.add_argument("--output", default="ml/results/v203-geometric-retrieval.json")
    args = parser.parse_args()
    data = load_prepared(args.data)
    result = {"contract": {"classes": list(data.label_names), "sequences": len(data.labels), "frames": int(sum(map(len, data.sequences))),
                            "feature_shape": [T, D], "signers": sorted(set(data.signers.tolist()))}, "table": dataset_table(data), "experiments": []}
    for rep in ("raw", "wrist_scale", "local_hand", "angular", "motion"):
        for family in ("flat", "stats"):
            result["experiments"].append(run_experiment(data, rep, family, "euclidean"))
    result["random_baseline"] = random_metrics(len(data.labels), len(CLASSES))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(out), "sequences": len(data.labels), "experiments": len(result["experiments"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
