"""Loader and audit helpers for LiFbras Capture references (schema v1/v2)."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
CLASSES = ("2_Sim", "7_Quero", "92_Energia", "110_Menos", "111_Mais")


def migrar_referencia(item: dict) -> dict:
    """Map a valid V2.07 labeled record to v2 without changing its capture."""
    if not isinstance(item, dict):
        raise ValueError("reference must be an object")
    if item.get("versao") == LEGACY_SCHEMA_VERSION:
        legacy = dict(item)
        legacy.update(versao=SCHEMA_VERSION, tipo="referencia_rotulada", usarEmDataset=True, migradoDe=1)
        validar_schema(legacy)
        return legacy
    validar_schema(item)
    return item


def validar_schema(item: dict) -> None:
    if not isinstance(item, dict) or item.get("versao") != SCHEMA_VERSION:
        raise ValueError("unsupported reference schema version")
    required = ("referenciaId", "tipo", "usarEmDataset", "sinalId", "signerId", "tentativa", "criadoEm", "validacao", "captura")
    if any(key not in item for key in required):
        raise ValueError("missing required reference field")
    if not isinstance(item["referenciaId"], str) or not isinstance(item["signerId"], str) or not isinstance(item["captura"], dict):
        raise ValueError("invalid identity or capture fields")
    if not isinstance(item["captura"].get("duracaoMs"), (int, float)) or not isinstance(item["captura"].get("frames"), list):
        raise ValueError("invalid capture fields")
    if not isinstance(item["validacao"], dict) or not isinstance(item["validacao"].get("status"), str):
        raise ValueError("invalid validation fields")
    if item["tipo"] == "teste_tecnico":
        if item["usarEmDataset"] is not False or item["sinalId"] is not None or item["tentativa"] is not None:
            raise ValueError("technical test must be unlabeled and excluded from dataset")
    elif item["tipo"] == "referencia_rotulada":
        if item["usarEmDataset"] is not True or item["sinalId"] not in CLASSES or not isinstance(item["tentativa"], int) or isinstance(item["tentativa"], bool) or item["tentativa"] < 1:
            raise ValueError("labeled reference requires a known class and dataset inclusion")
        if item.get("migradoDe") != 1:
            reference = item.get("referenciaDidatica")
            if not isinstance(reference, dict) or reference.get("disponivel") is not True or reference.get("tipo") not in ("imagem", "video", "sequencia", "gif") or not isinstance(reference.get("origem"), str) or not reference["origem"]:
                raise ValueError("labeled reference requires an identified didactic reference")
    else:
        raise ValueError("invalid reference type")


def carregar_referencias_completas(path: str | Path) -> list[dict]:
    parsed = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("reference export must be a JSON array")
    normalized = [migrar_referencia(item) for item in parsed]
    ids = [item["referenciaId"] for item in normalized]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate referenceId")
    return normalized


def carregar_referencias(path: str | Path) -> list[dict]:
    """Load labeled dataset records only; technical captures are excluded by default."""
    return [item for item in carregar_referencias_completas(path) if item["tipo"] == "referencia_rotulada" and item["usarEmDataset"] is True]


def carregar_referencias_rotuladas(path: str | Path) -> list[dict]:
    return carregar_referencias(path)


def frame_array(item: dict) -> np.ndarray:
    validar_schema(item)
    frames = item["captura"]["frames"]
    output = np.zeros((len(frames), 2, 21, 3), dtype=np.float32)
    for t, frame in enumerate(frames):
        for hand, key in enumerate(("maoEsquerda", "maoDireita")):
            points = frame.get(key)
            if points is None:
                continue
            if not isinstance(points, list) or len(points) != 21:
                raise ValueError("hand must contain 21 landmarks")
            for p, point in enumerate(points):
                if not all(isinstance(point.get(axis), (int, float)) for axis in ("x", "y", "z")):
                    raise ValueError("invalid landmark coordinate")
                output[t, hand, p] = [point[axis] for axis in ("x", "y", "z")]
    if not np.isfinite(output).all():
        raise ValueError("landmarks contain NaN/Inf")
    return output


def agrupar_por_signer(referencias: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for item in referencias:
        grouped[item["signerId"]].append(item)
    return dict(grouped)


def agrupar_por_sinal(referencias: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for item in referencias:
        if item["tipo"] == "referencia_rotulada":
            grouped[item["sinalId"]].append(item)
    return dict(grouped)


def hash_captura(item: dict) -> str:
    return hashlib.sha256(json.dumps(item["captura"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def detectar_duplicatas(referencias: list[dict]) -> list[list[str]]:
    groups = defaultdict(list)
    for item in referencias:
        groups[hash_captura(item)].append(item["referenciaId"])
    return [ids for ids in groups.values() if len(ids) > 1]


def split_por_signer(referencias: list[dict], test_signer: str) -> tuple[list[dict], list[dict]]:
    test = [item for item in referencias if item["signerId"] == test_signer]
    train = [item for item in referencias if item["signerId"] != test_signer]
    if any(a["signerId"] == test_signer for a in train):
        raise AssertionError("signer leakage")
    return train, test


def resumo(referencias: list[dict]) -> dict:
    labeled = [item for item in referencias if item["tipo"] == "referencia_rotulada" and item["usarEmDataset"] is True]
    technical = [item for item in referencias if item["tipo"] == "teste_tecnico"]
    arrays = [frame_array(item) for item in labeled]
    lengths = [len(array) for array in arrays]
    hand_counts = [np.count_nonzero(np.any(array != 0, axis=(2, 3)), axis=1) for array in arrays]
    return {"signers": len(agrupar_por_signer(labeled)), "signs": len(agrupar_por_sinal(labeled)), "sequences": len(labeled), "technical_sequences": len(technical), "by_signer": Counter(item["signerId"] for item in labeled), "by_sign": Counter(item["sinalId"] for item in labeled), "frames": {"min": min(lengths, default=0), "mean": float(np.mean(lengths)) if lengths else 0, "median": float(np.median(lengths)) if lengths else 0, "max": max(lengths, default=0)}, "hand_presence": {str(n): int(sum(np.sum(counts == n) for counts in hand_counts)) for n in (0, 1, 2)}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--debug-all", action="store_true", help="include technical tests in raw validation output")
    args = parser.parse_args()
    refs = carregar_referencias_completas(args.path) if args.debug_all else carregar_referencias(args.path)
    print(json.dumps(resumo(refs), indent=2, ensure_ascii=False, default=dict))


if __name__ == "__main__":
    main()
