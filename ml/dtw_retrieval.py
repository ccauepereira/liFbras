"""Small, auditable DTW retrieval experiment for LiFbras V2.04."""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from multiprocessing import Pool, cpu_count
from pathlib import Path

import numpy as np

try:
    from numba import njit
except ImportError:  # optional accelerator; pure NumPy/Python remains canonical
    njit = None

try:
    from .retrieval_baseline import (
        CLASSES, PreparedData, angular, descriptor, distance, load_prepared,
        local_hand, medoid_indices, motion, rank_instances, random_metrics,
        run_experiment,
    )
except ImportError:
    from retrieval_baseline import (
        CLASSES, PreparedData, angular, descriptor, distance, load_prepared,
        local_hand, medoid_indices, motion, rank_instances, random_metrics,
        run_experiment,
    )


def _local(a: np.ndarray, b: np.ndarray, metric: str) -> float:
    if metric == "euclidean":
        return float(np.linalg.norm(a - b))
    if metric == "manhattan":
        return float(np.abs(a - b).sum())
    if metric == "cosine":
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 and nb == 0:
            return 0.0
        if na == 0 or nb == 0:
            return 1.0
        return float(1.0 - np.dot(a, b) / (na * nb))
    raise ValueError(f"unknown local metric: {metric}")


def dtw_distance(a: np.ndarray, b: np.ndarray, metric: str = "euclidean",
                 band_fraction: float | None = None, normalize: bool = False) -> dict:
    """Return DTW distance, path, and path length for two finite [T,F] arrays."""
    x, y = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 2 or x.shape[1] != y.shape[1] or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("DTW inputs must be finite [T,F] arrays with equal F")
    if band_fraction is not None and (band_fraction < 0 or band_fraction > 1):
        raise ValueError("band_fraction must be in [0,1]")
    n, m = len(x), len(y)
    if njit is not None:
        metric_code = {"euclidean": 0, "manhattan": 1}.get(metric)
        if metric_code is not None:
            radius = -1 if band_fraction is None else int(np.ceil(band_fraction * max(n, m)))
            cost, prev = _dtw_numba(x, y, metric_code, radius)
            if not np.isfinite(cost[n, m]):
                raise ValueError("Sakoe-Chiba band produced no valid path")
            path = []
            i, j = n, m
            while i or j:
                path.append((i - 1, j - 1))
                i, j = map(int, prev[i, j])
            path.reverse()
            length = len(path)
            raw = float(cost[n, m])
            return {"distance": raw / length if normalize else raw, "raw_distance": raw,
                    "path": path, "path_length": length, "normalized": normalize,
                    "band_fraction": band_fraction}
    inf = float("inf")
    cost = np.full((n + 1, m + 1), inf)
    steps = np.zeros((n + 1, m + 1), dtype=np.int32)
    prev = np.zeros((n + 1, m + 1, 2), dtype=np.int32)
    cost[0, 0] = 0.0
    radius = None if band_fraction is None else int(np.ceil(band_fraction * max(n, m)))
    # Anti-diagonal dynamic programming: all cells on one anti-diagonal depend
    # only on earlier anti-diagonals, so NumPy handles each vector at once.
    pairwise = np.linalg.norm(x[:, None, :] - y[None, :, :], axis=2) if metric == "euclidean" else np.abs(x[:, None, :] - y[None, :, :]).sum(axis=2)
    if metric == "cosine":
        nx, ny = np.linalg.norm(x, axis=1), np.linalg.norm(y, axis=1)
        denom = nx[:, None] * ny[None, :]
        pairwise = np.where(denom == 0, np.where((nx[:, None] == 0) & (ny[None, :] == 0), 0.0, 1.0), 1.0 - (x @ y.T) / denom)
    for k in range(2, n + m + 1):
        lo_i, hi_i = max(1, k - m), min(n, k - 1)
        ii = np.arange(lo_i, hi_i + 1)
        jj = k - ii
        allowed = np.ones(len(ii), dtype=bool)
        if radius is not None:
            center = (ii - 1) * (m - 1) / max(1, n - 1) + 1
            allowed = np.abs(jj - center) <= radius
        if not allowed.any():
            continue
        ii, jj = ii[allowed], jj[allowed]
        up, left, diag = cost[ii - 1, jj], cost[ii, jj - 1], cost[ii - 1, jj - 1]
        choices = np.stack((up, left, diag), axis=0)
        pick = np.argmin(choices, axis=0)
        cost[ii, jj] = pairwise[ii - 1, jj - 1] + choices[pick, np.arange(len(pick))]
        for code, di, dj in ((0, -1, 0), (1, 0, -1), (2, -1, -1)):
            chosen = pick == code
            prev[ii[chosen], jj[chosen]] = np.column_stack((ii[chosen] + di, jj[chosen] + dj))
    if not np.isfinite(cost[n, m]):
        raise ValueError("Sakoe-Chiba band produced no valid path")
    path = []
    i, j = n, m
    while i or j:
        path.append((i - 1, j - 1))
        i, j = map(int, prev[i, j])
    path.reverse()
    length = len(path)
    raw = float(cost[n, m])
    return {"distance": raw / length if normalize else raw, "raw_distance": raw,
            "path": path, "path_length": length, "normalized": normalize,
            "band_fraction": band_fraction}


def representation_sequence(sequence: np.ndarray, name: str, resampled: bool = False) -> np.ndarray:
    """Build a selected temporal representation without forcing resampling."""
    x = np.asarray(sequence, dtype=np.float32)
    # Import locally so direct script execution and package tests both work.
    try:
        from .preprocessamento import preprocessar_sequencia, reamostrar_temporal
    except ImportError:
        from preprocessamento import preprocessar_sequencia, reamostrar_temporal
    if resampled:
        x = reamostrar_temporal(x, tamanho=60, dimensao=126)
    if name == "wrist_scale":
        return preprocessar_sequencia(x, "wrist_scale", tamanho=len(x))
    if name == "local_global_motion":
        return np.concatenate((local_hand(x), motion(x)), axis=1)
    if name == "motion":
        return motion(x)
    if name == "angular":
        return angular(x)
    if name == "position_motion":
        return np.concatenate((preprocessar_sequencia(x, "wrist_scale", tamanho=len(x)), motion(x)), axis=1)
    raise ValueError(f"unknown DTW representation: {name}")


def _metrics(ranking: list[dict], true_label: int) -> dict:
    labels = [r["label"] for r in ranking]
    rank = labels.index(true_label) + 1 if true_label in labels else len(labels) + 1
    return {"r1": int(rank == 1), "r3": int(rank <= 3), "mrr": 1.0 / rank, "rank": rank}


def _summary(rows: list[dict]) -> dict:
    def avg(items):
        return {k: float(np.mean([r["metrics"][k] for r in items])) for k in ("r1", "r3", "mrr")}
    return {
        "overall": avg(rows),
        "per_class": {str(c): avg([r for r in rows if r["class"] == c]) for c in sorted({r["class"] for r in rows})},
        "per_signer": {str(s): avg([r for r in rows if r["signer"] == s]) for s in sorted({r["signer"] for r in rows})},
    }


def _class_ranking(scored: list[dict], k: int, mode: str) -> list[dict]:
    grouped = defaultdict(list)
    for item in scored:
        grouped[item["label"]].append(item["distance"])
    ranked = []
    for label, values in grouped.items():
        values = values[:k]
        ranked.append({"label": label, "distance": min(values) if mode == "best" else float(np.mean(values))})
    return sorted(ranked, key=lambda x: (x["distance"], x["label"]))


_WORKER = {}

if njit is not None:
    @njit(cache=False)
    def _dtw_numba(x, y, metric_code, radius):
        n, m, f = x.shape[0], y.shape[0], x.shape[1]
        inf = 1e300
        cost = np.full((n + 1, m + 1), inf)
        prev = np.zeros((n + 1, m + 1, 2), dtype=np.int32)
        cost[0, 0] = 0.0
        for i in range(1, n + 1):
            center = (i - 1) * (m - 1) / max(1, n - 1) + 1.0
            lo = 1 if radius < 0 else max(1, int(np.ceil(center - radius)))
            hi = m if radius < 0 else min(m, int(np.floor(center + radius)))
            for j in range(lo, hi + 1):
                up, left, diag = cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1]
                best, pi, pj = up, i - 1, j
                if left < best: best, pi, pj = left, i, j - 1
                if diag < best: best, pi, pj = diag, i - 1, j - 1
                local = 0.0
                for q in range(f):
                    delta = x[i - 1, q] - y[j - 1, q]
                    local += abs(delta) if metric_code == 1 else delta * delta
                if metric_code == 0: local = np.sqrt(local)
                cost[i, j] = local + best
                prev[i, j, 0], prev[i, j, 1] = pi, pj
        return cost, prev


def _init_worker(features, gids, labels, signers, sources, metric, band_fraction, normalize, held):
    _WORKER.update(features=features, gids=gids, labels=labels, signers=signers, sources=sources,
                   metric=metric, band_fraction=band_fraction, normalize=normalize, held=held)


def _one_query_worker(qi):
    features, gids = _WORKER["features"], _WORKER["gids"]
    scored = []
    for gi in gids:
        d = dtw_distance(features[qi], features[gi], _WORKER["metric"], _WORKER["band_fraction"], _WORKER["normalize"])
        scored.append({"index": gi, "label": int(_WORKER["labels"][gi]), "signer": str(_WORKER["signers"][gi]),
                       "source_file": str(_WORKER["sources"][gi]), "distance": d["distance"],
                       "raw_distance": d["raw_distance"], "path_length": d["path_length"]})
    scored.sort(key=lambda r: (r["distance"], r["index"]))
    d1, d2 = scored[0]["distance"], scored[1]["distance"]
    label = int(_WORKER["labels"][qi])
    return {"query": qi, "signer": _WORKER["held"], "class": label, "metrics": _metrics(scored, label),
            "top_classes": [r["label"] for r in scored[:3]], "top_instances": scored[:3],
            "_all_instances": scored, "d1": d1, "d2": d2, "margin": d2 - d1, "ratio": d1 / d2 if d2 else 0.0}


def evaluate(data: PreparedData, representation: str, metric: str = "euclidean",
             normalize: bool = True, band_fraction: float | None = None,
             resampled: bool = False) -> dict:
    features = [representation_sequence(s, representation, resampled) for s in data.sequences]
    rows, medoid_rows = [], []
    for held in sorted(set(data.signers.tolist())):
        qids = [i for i, s in enumerate(data.signers) if s == held]
        gids = [i for i, s in enumerate(data.signers) if s != held]
        gallery = [features[i] for i in gids]
        if njit is not None:
            _init_worker(features, gids, data.labels, data.signers, data.source_files, metric, band_fraction, normalize, held)
            rows.extend(_one_query_worker(qi) for qi in qids)
        else:
            with Pool(processes=min(8, cpu_count(), len(qids)), initializer=_init_worker,
                      initargs=(features, gids, data.labels, data.signers, data.source_files, metric, band_fraction, normalize, held)) as pool:
                rows.extend(pool.map(_one_query_worker, qids))
        # Real class medoids: choose an observed gallery sequence by pairwise DTW.
        for label in range(len(CLASSES)):
            ids = [i for i in gids if int(data.labels[i]) == label]
            medoid = min(ids, key=lambda candidate: np.mean([dtw_distance(features[candidate], features[j], metric, band_fraction, normalize)["distance"] for j in ids]))
            for qi in qids:
                medoid_rows.append({"query": qi, "signer": held, "class": int(data.labels[qi]), "medoid_label": label,
                                    "distance": dtw_distance(features[qi], features[medoid], metric, band_fraction, normalize)["distance"]})
    medoid_summary_rows = []
    for qi in sorted({r["query"] for r in medoid_rows}):
        candidates = [r for r in medoid_rows if r["query"] == qi]
        ranking = [{"label": r["medoid_label"], "distance": r["distance"]} for r in candidates]
        q = candidates[0]
        medoid_summary_rows.append({"query": qi, "signer": q["signer"], "class": q["class"], "metrics": _metrics(sorted(ranking, key=lambda r: (r["distance"], r["label"])), q["class"])})
    aggregation = {}
    aggregation_rows = {}
    for mode in ("best", "mean"):
        for k in (1, 3):
            class_rows = []
            for row in rows:
                ranking = _class_ranking(row["top_instances"] + [], k, mode)
                # top_instances is only a trace; recompute aggregation from all
                # candidates when available in the internal row payload.
                full = row.get("_all_instances", row["top_instances"])
                ranking = _class_ranking(full, k, mode)
                class_rows.append({"query": row["query"], "signer": row["signer"], "class": row["class"], "metrics": _metrics(ranking, row["class"])})
            aggregation[f"{mode}_k{k}"] = _summary(class_rows)
            aggregation_rows[f"{mode}_k{k}"] = class_rows
    for row in rows:
        row.pop("_all_instances", None)
    return {"representation": representation, "metric": metric, "normalize": normalize, "band_fraction": band_fraction,
            "resampled": resampled, "n_queries": len(rows), "summary": _summary(rows), "aggregation": aggregation,
            "medoid": _summary(medoid_summary_rows), "rows": rows, "aggregation_rows": aggregation_rows}


def ablation(data: PreparedData, metric: str, normalize: bool, band_fraction: float | None) -> dict:
    result = {}
    for name in ("wrist_scale", "motion", "position_motion"):
        result[name] = evaluate(data, name, metric, normalize, band_fraction)["aggregation"]["best_k1"]["overall"]
    return result


def latency(data: PreparedData, representation: str, metric: str, normalize: bool, band_fraction: float | None, n: int = 10) -> dict:
    feats = [representation_sequence(s, representation) for s in data.sequences]
    extraction, comparisons, ranking = [], [], []
    for qi in range(n):
        t = time.perf_counter(); query = representation_sequence(data.sequences[qi], representation); extraction.append((time.perf_counter() - t) * 1000)
        ids = [i for i, s in enumerate(data.signers) if s != data.signers[qi]]
        t = time.perf_counter(); scored = [dtw_distance(query, feats[i], metric, band_fraction, normalize)["distance"] for i in ids]; comparisons.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter(); sorted(scored); ranking.append((time.perf_counter() - t) * 1000)
    return {"comparisons_per_query": len(ids), "extraction_ms": {"median": float(np.median(extraction)), "p95": float(np.percentile(extraction, 95))},
            "dtw_query_gallery_ms": {"median": float(np.median(comparisons)), "p95": float(np.percentile(comparisons, 95))},
            "ranking_ms": {"median": float(np.median(ranking)), "p95": float(np.percentile(ranking, 95))}}


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--data", default="dataset/libras-eqt-uece/mvp-hand-landmarks.npz"); p.add_argument("--output", default="ml/results/v204-dtw-retrieval.json"); args = p.parse_args()
    data = load_prepared(args.data)
    # Main original-length runs: four justified representations, two local metrics.
    experiments = []
    configs = [("wrist_scale", "euclidean", True, None), ("wrist_scale", "manhattan", True, None),
               ("local_global_motion", "euclidean", True, None), ("motion", "euclidean", True, None),
               ("angular", "euclidean", True, None), ("position_motion", "euclidean", True, None),
               ("wrist_scale", "euclidean", True, 0.10), ("wrist_scale", "euclidean", True, 0.20)]
    for config in configs:
        print("running", config, flush=True); experiments.append(evaluate(data, *config))
    out = {"contract": {"sequences": len(data.labels), "frames": int(sum(map(len, data.sequences))), "classes": list(data.label_names), "signers": sorted(set(data.signers.tolist())), "feature_values": 126},
           "experiments": experiments, "random": random_metrics(len(data.labels), len(CLASSES)),
           "ablation": ablation(data, "euclidean", True, None),
           "latency": latency(data, "wrist_scale", "euclidean", True, None, n=5)}
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
