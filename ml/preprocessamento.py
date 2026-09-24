"""Canonical sequence preprocessing shared by training and future inference."""

from __future__ import annotations

import numpy as np


TAMANHO_TEMPORAL = 60
DIMENSAO_ENTRADA = 126
PONTOS_POR_MAO = 21
VALORES_POR_MAO = 63
DIMENSAO_POSE_MINIMA = 15
DIMENSAO_MAOS_POSE = DIMENSAO_ENTRADA + DIMENSAO_POSE_MINIMA
EPSILON_OMBROS = 1e-6


def reamostrar_temporal(sequencia: np.ndarray, tamanho: int = TAMANHO_TEMPORAL, dimensao: int = DIMENSAO_ENTRADA) -> np.ndarray:
    """Linearly resample a finite ``[frames, dimensao]`` array without randomness."""
    array = np.asarray(sequencia, dtype=np.float32)
    if array.ndim != 2 or array.shape[1] != dimensao or array.shape[0] < 1:
        raise ValueError(f"expected [frames, {dimensao}], received {array.shape}")
    if not np.isfinite(array).all():
        raise ValueError("sequence contains NaN or Inf")
    if tamanho < 1:
        raise ValueError("temporal size must be positive")
    if array.shape[0] == tamanho:
        return array.copy()
    posições = np.linspace(0, array.shape[0] - 1, tamanho, dtype=np.float32)
    inferiores = np.floor(posições).astype(np.int64)
    superiores = np.minimum(inferiores + 1, array.shape[0] - 1)
    pesos = (posições - inferiores).reshape(-1, 1)
    return array[inferiores] * (1.0 - pesos) + array[superiores] * pesos


def normalizar_trajetoria_preservada(sequencia: np.ndarray) -> np.ndarray:
    """Normalize hand shape while retaining each wrist's global trajectory.

    Wrist coordinates (landmark 0) remain in the original coordinate space.
    Other points are expressed relative to that wrist and a median palm scale.
    Missing zero blocks stay zero. This is the single comparison alternative
    selected by PROMPT 08 research; it does not erase global wrist movement.
    """
    resultado = np.asarray(sequencia, dtype=np.float32).copy()
    for inicio in (0, VALORES_POR_MAO):
        bloco = resultado[:, inicio : inicio + VALORES_POR_MAO].reshape(-1, PONTOS_POR_MAO, 3)
        presente = np.any(bloco != 0, axis=(1, 2))
        escalas = []
        for quadro, ativo in zip(bloco, presente):
            if ativo:
                distancia = np.linalg.norm(quadro[9] - quadro[0])
                if distancia > 1e-6:
                    escalas.append(float(distancia))
        escala = float(np.median(escalas)) if escalas else 1.0
        for indice, ativo in enumerate(presente):
            if not ativo:
                bloco[indice] = 0.0
                continue
            pulso = bloco[indice, 0].copy()
            bloco[indice, 1:] = (bloco[indice, 1:] - pulso) / escala
            bloco[indice, 0] = pulso
    return resultado.reshape(-1, DIMENSAO_ENTRADA)


def preprocessar_sequencia(
    sequencia: np.ndarray,
    variante: str = "raw",
    tamanho: int = TAMANHO_TEMPORAL,
) -> np.ndarray:
    """Return the canonical finite ``[60, 126]`` representation."""
    resultado = reamostrar_temporal(sequencia, tamanho=tamanho)
    if variante == "raw":
        pass
    elif variante == "wrist_scale":
        resultado = normalizar_trajetoria_preservada(resultado)
    else:
        raise ValueError(f"unknown preprocessing variant: {variante}")
    if not np.isfinite(resultado).all():
        raise ValueError("preprocessing introduced NaN or Inf")
    return resultado.astype(np.float32, copy=False)


def preprocessar_maos_pose(sequencia: np.ndarray, variante: str, tamanho: int = TAMANHO_TEMPORAL) -> np.ndarray:
    """Prepare the fixed 141-value experiment while retaining the hand contract.

    ``hand_pose`` keeps existing wrist-scale hands and appends raw selected pose
    coordinates. ``body_relative`` retains local finger geometry, substitutes
    each wrist by its shoulder-relative position, and expresses selected pose
    points in the same shoulder-centered coordinate system.
    """
    array = reamostrar_temporal(sequencia, tamanho=tamanho, dimensao=DIMENSAO_MAOS_POSE)
    maos_origem = array[:, :DIMENSAO_ENTRADA]
    pose = array[:, DIMENSAO_ENTRADA:].reshape(-1, 5, 3)
    maos_locais = normalizar_trajetoria_preservada(maos_origem)
    if variante == "hand_pose":
        resultado = np.concatenate((maos_locais, pose.reshape(-1, DIMENSAO_POSE_MINIMA)), axis=1)
    elif variante == "body_relative":
        ombro_esquerdo, ombro_direito = pose[:, 1], pose[:, 2]
        centro = (ombro_esquerdo + ombro_direito) / 2.0
        escala = np.linalg.norm(ombro_esquerdo - ombro_direito, axis=1)
        valido = escala > EPSILON_OMBROS
        pose_corpo = np.zeros_like(pose)
        pose_corpo[valido] = (pose[valido] - centro[valido, None, :]) / escala[valido, None, None]
        maos_corpo = maos_locais.reshape(-1, 2, PONTOS_POR_MAO, 3)
        maos_brutas = maos_origem.reshape(-1, 2, PONTOS_POR_MAO, 3)
        presenca = np.any(maos_brutas != 0, axis=(2, 3))
        for indice_mao in (0, 1):
            usar = presenca[:, indice_mao] & valido
            maos_corpo[:, indice_mao, 0] = 0.0
            maos_corpo[usar, indice_mao, 0] = (maos_brutas[usar, indice_mao, 0] - centro[usar]) / escala[usar, None]
        resultado = np.concatenate((maos_corpo.reshape(-1, DIMENSAO_ENTRADA), pose_corpo.reshape(-1, DIMENSAO_POSE_MINIMA)), axis=1)
    else:
        raise ValueError(f"unknown hand-pose variant: {variante}")
    if not np.isfinite(resultado).all():
        raise ValueError("hand-pose preprocessing introduced NaN or Inf")
    return resultado.astype(np.float32, copy=False)
