"""Minimal pose extraction shared by the PROMPT 08D offline experiment."""

from __future__ import annotations

import io
from pathlib import Path
from zipfile import ZipFile

import numpy as np


DIMENSAO_MAOS = 126
DIMENSAO_HOLISTIC = 318
DIMENSAO_POSE = 15
DIMENSAO_MAOS_POSE = DIMENSAO_MAOS + DIMENSAO_POSE
INDICES_POSE = (0, 11, 12, 13, 14)
NOMES_POSE = ("nose", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow")
FATIA_MAO_ESQUERDA = slice(192, 255)
FATIA_MAO_DIREITA = slice(255, 318)


def extrair_pose_minima(holistic: np.ndarray) -> np.ndarray:
    """Return nose, shoulders, and elbows as ``[frames, 15]`` float32."""
    array = np.asarray(holistic)
    if array.ndim != 2 or array.shape[1] != DIMENSAO_HOLISTIC:
        raise ValueError(f"expected [frames, {DIMENSAO_HOLISTIC}], received {array.shape}")
    if not np.isfinite(array).all():
        raise ValueError("holistic sequence contains NaN or Inf")
    pose = array[:, :99].reshape(-1, 33, 3)
    return pose[:, INDICES_POSE].reshape(-1, DIMENSAO_POSE).astype(np.float32, copy=False)


def combinar_maos_pose(maos: np.ndarray, holistic: np.ndarray) -> np.ndarray:
    """Verify the archived hand blocks and append the fixed 15-value pose order."""
    hands = np.asarray(maos)
    all_points = np.asarray(holistic)
    if hands.ndim != 2 or hands.shape[1] != DIMENSAO_MAOS:
        raise ValueError(f"expected [frames, {DIMENSAO_MAOS}], received {hands.shape}")
    if hands.shape[0] != all_points.shape[0]:
        raise ValueError("hand and holistic frame counts differ")
    if not np.isfinite(hands).all():
        raise ValueError("hand sequence contains NaN or Inf")
    if not np.array_equal(hands[:, :63], all_points[:, FATIA_MAO_ESQUERDA]) or not np.array_equal(hands[:, 63:], all_points[:, FATIA_MAO_DIREITA]):
        raise ValueError("hand blocks do not match the verified holistic layout")
    return np.concatenate((hands, extrair_pose_minima(all_points)), axis=1).astype(np.float32, copy=False)


def carregar_sequencias_maos_pose(caminho_zip: Path, fontes: list[str], sequencias_maos: list[np.ndarray]) -> list[np.ndarray]:
    """Load only the matching Holistic records needed by the local MVP."""
    if len(fontes) != len(sequencias_maos):
        raise ValueError("source paths and hand sequences differ in length")
    sequencias = []
    with ZipFile(caminho_zip) as archive:
        nomes = set(archive.namelist())
        for fonte, maos in zip(fontes, sequencias_maos):
            caminho_holistic = fonte.replace("Libras-EQT-UECE (Hand Landmarks)", "Libras-EQT-UECE (Landmarks)")
            if caminho_holistic not in nomes:
                raise ValueError(f"missing matching holistic file: {caminho_holistic}")
            holistic = np.load(io.BytesIO(archive.read(caminho_holistic)), allow_pickle=False)
            sequencias.append(combinar_maos_pose(maos, holistic))
    return sequencias
