"""Loader and audit helpers for local LiFbras Capture v1 references."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


SCHEMA_VERSION = 1
CLASSES = ("2_Sim", "7_Quero", "92_Energia", "110_Menos", "111_Mais")


def validar_schema(item: dict) -> None:
    if not isinstance(item, dict) or item.get("versao") != SCHEMA_VERSION:
        raise ValueError("unsupported reference schema version")
    required = ("referenciaId", "sinalId", "gloss", "signerId", "tentativa", "criadoEm", "validacao", "captura")
    if any(key not in item for key in required): raise ValueError("missing required reference field")
    if item["sinalId"] not in CLASSES or not isinstance(item["signerId"], str) or not isinstance(item["tentativa"], int): raise ValueError("invalid identity fields")
    if not isinstance(item["captura"].get("frames"), list) or not isinstance(item["validacao"].get("status"), str): raise ValueError("invalid capture or validation fields")


def carregar_referencias(path: str | Path) -> list[dict]:
    parsed = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(parsed, list): raise ValueError("reference export must be a JSON array")
    for item in parsed: validar_schema(item)
    ids = [item["referenciaId"] for item in parsed]
    if len(ids) != len(set(ids)): raise ValueError("duplicate referenceId")
    return parsed


def frame_array(item: dict) -> np.ndarray:
    validar_schema(item); frames = item["captura"]["frames"]; output = np.zeros((len(frames), 2, 21, 3), dtype=np.float32)
    for t, frame in enumerate(frames):
        for hand, key in enumerate(("maoEsquerda", "maoDireita")):
            points = frame.get(key)
            if points is None: continue
            if not isinstance(points, list) or len(points) != 21: raise ValueError("hand must contain 21 landmarks")
            for p, point in enumerate(points):
                if not all(isinstance(point.get(axis), (int, float)) for axis in ("x", "y", "z")): raise ValueError("invalid landmark coordinate")
                output[t, hand, p] = [point[axis] for axis in ("x", "y", "z")]
    if not np.isfinite(output).all(): raise ValueError("landmarks contain NaN/Inf")
    return output


def agrupar_por_signer(referencias: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for item in referencias: grouped[item["signerId"]].append(item)
    return dict(grouped)


def agrupar_por_sinal(referencias: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for item in referencias: grouped[item["sinalId"]].append(item)
    return dict(grouped)


def hash_captura(item: dict) -> str:
    return hashlib.sha256(json.dumps(item["captura"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def detectar_duplicatas(referencias: list[dict]) -> list[list[str]]:
    groups = defaultdict(list)
    for item in referencias: groups[hash_captura(item)].append(item["referenciaId"])
    return [ids for ids in groups.values() if len(ids) > 1]


def split_por_signer(referencias: list[dict], test_signer: str) -> tuple[list[dict], list[dict]]:
    test = [item for item in referencias if item["signerId"] == test_signer]; train = [item for item in referencias if item["signerId"] != test_signer]
    if any(a["signerId"] == test_signer for a in train): raise AssertionError("signer leakage")
    return train, test


def resumo(referencias: list[dict]) -> dict:
    arrays = [frame_array(item) for item in referencias]; lengths = [len(array) for array in arrays]
    hand_counts = [np.count_nonzero(np.any(array != 0, axis=(2, 3)), axis=1) for array in arrays]
    return {"signers": len(agrupar_por_signer(referencias)), "signs": len(agrupar_por_sinal(referencias)), "sequences": len(referencias), "by_signer": Counter(item["signerId"] for item in referencias), "by_sign": Counter(item["sinalId"] for item in referencias), "frames": {"min": min(lengths, default=0), "mean": float(np.mean(lengths)) if lengths else 0, "median": float(np.median(lengths)) if lengths else 0, "max": max(lengths, default=0)}, "hand_presence": {str(n): int(sum(np.sum(counts == n) for counts in hand_counts)) for n in (0, 1, 2)}}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("path"); args = parser.parse_args(); refs = carregar_referencias(args.path); print(json.dumps(resumo(refs), indent=2, ensure_ascii=False, default=dict))


if __name__ == "__main__": main()
