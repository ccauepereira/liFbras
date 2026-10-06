"""Deterministic robustness perturbations for the frozen LiFbras methods."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

try:
    from .dtw_retrieval import dtw_distance, representation_sequence
    from .embedding_retrieval import MLPEmbedding
    from .retrieval_baseline import CLASSES, PreparedData, descriptor, load_prepared
except ImportError:
    from dtw_retrieval import dtw_distance, representation_sequence
    from embedding_retrieval import MLPEmbedding
    from retrieval_baseline import CLASSES, PreparedData, descriptor, load_prepared


def _finite(x):
    x = np.asarray(x, dtype=np.float32)
    if not np.isfinite(x).all(): raise ValueError("perturbation introduced NaN/Inf")
    return x


def resample(x: np.ndarray, length: int) -> np.ndarray:
    try:
        from .preprocessamento import reamostrar_temporal
    except ImportError:
        from preprocessamento import reamostrar_temporal
    return reamostrar_temporal(x, max(1, int(length)), x.shape[1])


def speed(x, factor): return resample(x, round(len(x) * factor))


def random_drop(x, fraction, seed):
    rng = np.random.default_rng(seed); keep = rng.random(len(x)) >= fraction
    if not keep.any(): keep[rng.integers(len(x))] = True
    return x[keep]


def fps_subsample(x, fraction):
    return x[np.unique(np.linspace(0, len(x) - 1, max(1, round(len(x) * fraction))).astype(int))]


def contiguous_gap(x, fraction, position):
    n = max(1, round(len(x) * fraction)); start = {"start": 0, "middle": max(0, (len(x) - n) // 2), "end": max(0, len(x) - n)}[position]
    keep = np.ones(len(x), dtype=bool); keep[start:start + n] = False
    return x[keep] if keep.any() else x[[0]]


def hand_dropout(x, fraction, hand, position="middle"):
    out = x.copy(); n = max(1, round(len(x) * fraction)); start = {"start": 0, "middle": max(0, (len(x) - n) // 2), "end": max(0, len(x) - n)}[position]; out[start:start + n, hand * 63:(hand + 1) * 63] = 0.0; return out


def gaussian_noise(x, sigma, seed):
    x = _finite(x); rng = np.random.default_rng(seed); out = x.copy(); active = np.any(out != 0, axis=1); out[active] += rng.normal(0, sigma, out[active].shape).astype(np.float32); return _finite(out)


def translate(x, amount, axis):
    out = x.copy().reshape(len(x), 2, 21, 3); active = np.any(out != 0, axis=(1, 2, 3)); out[active, :, :, axis] += amount; return out.reshape(len(x), -1)


def scale(x, factor):
    out = x.copy().reshape(len(x), 2, 21, 3); active = np.any(out != 0, axis=(1, 2, 3)); center = out[active].mean(axis=(1, 2), keepdims=True); out[active] = center + factor * (out[active] - center); return out.reshape(len(x), -1)


def mirror(x, swap_hands=False):
    out = x.copy().reshape(len(x), 2, 21, 3); out[..., 0] = 1.0 - out[..., 0]
    return out[:, ::-1].copy().reshape(len(x), -1) if swap_hands else out.reshape(len(x), -1)


def rotate_xy(x, degrees):
    out = x.copy().reshape(len(x), 2, 21, 3); theta = np.deg2rad(degrees); c, s = np.cos(theta), np.sin(theta); active = np.any(out != 0, axis=(1, 2, 3)); center = out[active].mean(axis=(1, 2), keepdims=True); xy = out[active, ..., :2] - center[..., :2]; out[active, ..., 0] = center[..., 0] + c * xy[..., 0] - s * xy[..., 1]; out[active, ..., 1] = center[..., 1] + s * xy[..., 0] + c * xy[..., 1]; return out.reshape(len(x), -1)


def padding(x, fraction, side):
    n = max(1, round(len(x) * fraction)); prefix = np.repeat(x[:1], n, axis=0); suffix = np.repeat(x[-1:], n, axis=0)
    return np.concatenate((prefix, x), axis=0) if side == "prefix" else np.concatenate((x, suffix), axis=0) if side == "suffix" else np.concatenate((prefix, x, suffix), axis=0)


def perturbation(name, x, seed=42):
    if name == "clean": return x.copy()
    if name.startswith("speed_"): return speed(x, float(name.split("_")[1]))
    if name.startswith("drop_"): return random_drop(x, float(name.split("_")[1]), seed)
    if name.startswith("fps_"): return fps_subsample(x, float(name.split("_")[1]))
    if name.startswith("gap_"): _, fraction, pos = name.split("_"); return contiguous_gap(x, float(fraction), pos)
    if name.startswith("hand_"): _, fraction, hand, pos = name.split("_"); return hand_dropout(x, float(fraction), int(hand), pos)
    if name.startswith("noise_"): return gaussian_noise(x, float(name.split("_")[1]), seed)
    if name.startswith("trans_"): _, amount, axis = name.split("_"); return translate(x, float(amount), int(axis))
    if name.startswith("scale_"): return scale(x, float(name.split("_")[1]))
    if name == "mirror_x": return mirror(x, False)
    if name == "mirror_swap": return mirror(x, True)
    if name.startswith("rotate_"): return rotate_xy(x, float(name.split("_")[1]))
    if name.startswith("pad_"): _, frac, side = name.split("_"); return padding(x, float(frac), side)
    if name == "realistic_stress": return translate(gaussian_noise(fps_subsample(random_drop(x, .10, seed), .66), .005, seed), .02, 0)
    if name == "mobile_simulated": return fps_subsample(x, 19 / 30)
    raise ValueError(name)


def class_metrics(scores, true):
    classes = sorted(scores); order = sorted(classes, key=lambda c: (scores[c], c)); rank = order.index(int(true)) + 1; return {"r1": int(rank == 1), "r3": int(rank <= 3), "mrr": 1.0 / rank, "order": order, "d1": scores[order[0]], "d2": scores[order[1]]}


def load_mlp_checkpoints(signers):
    models = {}
    for signer in signers:
        p = Path("ml/results/v205-checkpoints") / f"mlp-{signer.replace(' ', '_')}.pt"; ckpt = torch.load(p, map_location="cpu", weights_only=False); model = MLPEmbedding(504, 64); model.load_state_dict(ckpt["state_dict"]); model.eval(); models[signer] = (model, ckpt["mean"], ckpt["std"])
    return models


def evaluate_method(data: PreparedData, method: str, scenario: str, seed: int = 42) -> dict:
    clean = data.sequences; rows = []
    mlp_models = load_mlp_checkpoints(sorted(set(data.signers.tolist()))) if method == "v205" else None
    for held in sorted(set(data.signers.tolist())):
        gids = [i for i, s in enumerate(data.signers) if s != held]; qids = [i for i, s in enumerate(data.signers) if s == held]
        if method == "v203":
            gallery = [descriptor(representation_sequence(clean[i], "wrist_scale", True), "stats") for i in gids]
        elif method == "v204":
            gallery = [representation_sequence(clean[i], "local_global_motion", False) for i in gids]
        else:
            model, mean, std = mlp_models[held]; gx = np.stack([descriptor(representation_sequence(clean[i], "wrist_scale", True), "stats") for i in gids]); gx = (gx - mean) / std
            with torch.no_grad(): gallery = model(torch.from_numpy(gx).float()).numpy()
        for qi in qids:
            qraw = _finite(perturbation(scenario, clean[qi], seed + qi));
            if method == "v203":
                q = descriptor(representation_sequence(qraw, "wrist_scale", True), "stats"); scores = {c: min(np.sum(np.abs(q - gallery[j])) for j, gi in enumerate(gids) if data.labels[gi] == c) for c in range(len(CLASSES))}
            elif method == "v204":
                q = representation_sequence(qraw, "local_global_motion", False); scores = {c: min(dtw_distance(q, gallery[j], "euclidean", None, True)["distance"] for j, gi in enumerate(gids) if data.labels[gi] == c) for c in range(len(CLASSES))}
            else:
                model, mean, std = mlp_models[held]; qf = descriptor(representation_sequence(qraw, "wrist_scale", True), "stats");
                with torch.no_grad(): q = model(torch.from_numpy(((qf - mean) / std)[None]).float()).numpy()[0]
                scores = {c: float(1.0 - np.max(q @ gallery[np.where(data.labels[gids] == c)[0]].T)) for c in range(len(CLASSES))}
            m = class_metrics(scores, data.labels[qi]); rows.append({"query": qi, "signer": held, "class": int(data.labels[qi]), "metrics": m, "top": m["order"][:3]})
    return {"method": method, "scenario": scenario, "seed": seed, "summary": summarize(rows), "rows": rows}


def summarize(rows):
    def avg(rs): return {k: float(np.mean([r["metrics"][k] for r in rs])) for k in ("r1", "r3", "mrr")}
    return {"overall": avg(rows), "per_signer": {str(s): avg([r for r in rows if r["signer"] == s]) for s in sorted({r["signer"] for r in rows})}, "per_class": {str(c): avg([r for r in rows if r["class"] == c]) for c in sorted({r["class"] for r in rows})}}


def main():
    p = argparse.ArgumentParser(); p.add_argument("--data", default="dataset/libras-eqt-uece/mvp-hand-landmarks.npz"); p.add_argument("--output", default="ml/results/v206-stress-retrieval.json"); args = p.parse_args(); data = load_prepared(args.data)
    scenarios = ["clean", "speed_0.6", "speed_0.8", "speed_1.2", "speed_1.5", "drop_0.1", "drop_0.2", "drop_0.3", "fps_0.66", "fps_0.5", "fps_0.33", "gap_0.05_start", "gap_0.1_middle", "gap_0.2_end", "hand_0.1_0_middle", "hand_0.2_1_middle", "hand_0.3_0_end", "noise_0.002", "noise_0.005", "noise_0.010", "trans_0.02_0", "trans_-0.02_1", "scale_0.9", "scale_1.1", "mirror_x", "mirror_swap", "rotate_5", "rotate_-10", "pad_0.05_prefix", "pad_0.1_suffix", "pad_0.1_both", "realistic_stress", "mobile_simulated"]
    results = []
    for method in ("v203", "v204", "v205"):
        for scenario in scenarios:
            print(method, scenario, flush=True); results.append(evaluate_method(data, method, scenario))
    out = {"contract": {"sequences": len(data.labels), "frames": int(sum(map(len, data.sequences))), "classes": list(data.label_names), "signers": sorted(set(data.signers.tolist()))}, "scenarios": scenarios, "results": results}
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"); print(path)


if __name__ == "__main__": main()
