"""Run the fixed minimal-pose leave-one-signer-out experiment for PROMPT 08D."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from diagnosticar_generalizacao import analise_pca
from modelo import BaselineMediaMLP
from pose import DIMENSAO_MAOS_POSE, NOMES_POSE, carregar_sequencias_maos_pose
from preprocessamento import DIMENSAO_ENTRADA, preprocessar_maos_pose, preprocessar_sequencia
from treinar import ARQUIVO_DADOS, CLASSES_ESPERADAS, avaliar, carregar_dataset, fixar_semente


RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_ZIP = RAIZ / "dataset/libras-eqt-uece/Landmarks.zip"
CAMINHO_RESULTADOS = RAIZ / "ml/results/prompt08d-pose.json"
EPOCHS = 30
TAMANHO_BATCH = 16
SEMENTE = 42


class DatasetRepresentacao(Dataset):
    def __init__(self, sequencias, labels, indices, transformar) -> None:
        self.sequencias = sequencias
        self.labels = labels
        self.indices = list(indices)
        self.transformar = transformar

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, indice: int):
        original = self.indices[indice]
        return torch.from_numpy(self.transformar(self.sequencias[original])), torch.tensor(int(self.labels[original]), dtype=torch.long)


def criar_loader(sequencias, labels, indices, transformar, shuffle: bool) -> DataLoader:
    return DataLoader(
        DatasetRepresentacao(sequencias, labels, indices, transformar),
        batch_size=TAMANHO_BATCH,
        shuffle=shuffle,
        generator=torch.Generator().manual_seed(SEMENTE) if shuffle else None,
    )


def resumo_metricas(resultados: dict[str, dict]) -> dict:
    f1 = np.asarray([resultado["macro_f1"] for resultado in resultados.values()], dtype=np.float64)
    return {
        "mean_macro_f1": float(f1.mean()),
        "median_macro_f1": float(np.median(f1)),
        "min_macro_f1": float(f1.min()),
        "max_macro_f1": float(f1.max()),
        "std_macro_f1": float(f1.std()),
    }


def rotacao_lopo(nome, sequencias, labels, signers, classes, transformar, input_size: int) -> dict:
    """Fixed 30-epoch MLP protocol; only the input representation changes."""
    resultados = {}
    for signer_teste in sorted(set(signers.tolist())):
        indices_treino = [indice for indice, signer in enumerate(signers) if signer != signer_teste]
        indices_teste = [indice for indice, signer in enumerate(signers) if signer == signer_teste]
        fixar_semente(SEMENTE)
        modelo = BaselineMediaMLP(input_size=input_size, hidden_size=64, num_classes=len(classes))
        treino = criar_loader(sequencias, labels, indices_treino, transformar, True)
        criterio = nn.CrossEntropyLoss()
        otimizador = torch.optim.AdamW(modelo.parameters(), lr=1e-3, weight_decay=1e-4)
        for _ in range(EPOCHS):
            modelo.train()
            for entradas, rotulos in treino:
                otimizador.zero_grad(set_to_none=True)
                perda = criterio(modelo(entradas), rotulos)
                perda.backward()
                otimizador.step()
        resultados[signer_teste] = avaliar(modelo, criar_loader(sequencias, labels, indices_teste, transformar, False), len(classes), True)
    return {"name": nome, "input_size": input_size, "per_signer": resultados, "aggregate": resumo_metricas(resultados)}


def estatisticas_pose(sequencias, labels, signers, classes) -> dict:
    grupos = defaultdict(list)
    for sequencia, label, signer in zip(sequencias, labels, signers):
        grupos[(str(signer), classes[int(label)])].append(sequencia[:, DIMENSAO_ENTRADA:].reshape(-1, 5, 3))
    resultado = {}
    for (signer, classe), amostras in sorted(grupos.items()):
        pontos = np.concatenate(amostras, axis=0)
        resultado[f"{signer} | {classe}"] = {
            "frames": int(pontos.shape[0]),
            "nan_or_inf": int((~np.isfinite(pontos)).sum()),
            "all_pose_zero_frames": int(np.all(pontos == 0, axis=(1, 2)).sum()),
            "points": {
                nome: {
                    "zero_frames": int(np.all(pontos[:, indice] == 0, axis=1).sum()),
                    "zero_rate": float(np.mean(np.all(pontos[:, indice] == 0, axis=1))),
                    "coordinate_min": pontos[:, indice].min(axis=0).tolist(),
                    "coordinate_max": pontos[:, indice].max(axis=0).tolist(),
                }
                for indice, nome in enumerate(NOMES_POSE)
            },
            "shoulder_scale_min": float(np.linalg.norm(pontos[:, 1] - pontos[:, 2], axis=1).min()),
        }
    return resultado


def representacoes_temporais(sequencias, transformar) -> np.ndarray:
    return np.asarray([transformar(sequencia).mean(axis=0) for sequencia in sequencias])


def executar() -> dict:
    torch.set_num_threads(1)
    maos, labels, signers, classes = carregar_dataset(ARQUIVO_DADOS)
    if classes != CLASSES_ESPERADAS:
        raise ValueError("class order changed")
    fontes = np.load(ARQUIVO_DADOS, allow_pickle=False)["source_files"].tolist()
    maos_pose = carregar_sequencias_maos_pose(ARQUIVO_ZIP, fontes, maos)
    if any(sequencia.shape[1] != DIMENSAO_MAOS_POSE for sequencia in maos_pose):
        raise ValueError("augmented feature size changed")

    transformadores = {
        "hand_only": lambda sequencia: preprocessar_sequencia(sequencia, variante="wrist_scale"),
        "hand_pose": lambda sequencia: preprocessar_maos_pose(sequencia, variante="hand_pose"),
        "body_relative": lambda sequencia: preprocessar_maos_pose(sequencia, variante="body_relative"),
    }
    experimentos = {
        "hand_only": rotacao_lopo("hand_only", maos, labels, signers, classes, transformadores["hand_only"], DIMENSAO_ENTRADA),
        "hand_pose": rotacao_lopo("hand_pose", maos_pose, labels, signers, classes, transformadores["hand_pose"], DIMENSAO_MAOS_POSE),
        "body_relative": rotacao_lopo("body_relative", maos_pose, labels, signers, classes, transformadores["body_relative"], DIMENSAO_MAOS_POSE),
    }
    pca = {
        nome: analise_pca(representacoes_temporais(maos if nome == "hand_only" else maos_pose, transformador), labels, signers, classes)
        for nome, transformador in transformadores.items()
    }
    resultado = {
        "protocol": {"model": "BaselineMediaMLP  input→64→5 with temporal mean", "epochs": EPOCHS, "batch_size": TAMANHO_BATCH, "optimizer": "AdamW(lr=0.001, weight_decay=0.0001)", "seed": SEMENTE, "class_order": classes},
        "verified_layout": {"records": len(maos_pose), "holistic": "pose[0:99] + face[99:192] + left_hand[192:255] + right_hand[255:318]", "augmented_order": "left_hand[0:63], right_hand[63:126], nose[126:129], left_shoulder[129:132], right_shoulder[132:135], left_elbow[135:138], right_elbow[138:141]"},
        "pose_quality": estatisticas_pose(maos_pose, labels, signers, classes),
        "experiments": experimentos,
        "pca": pca,
    }
    CAMINHO_RESULTADOS.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_RESULTADOS.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


if __name__ == "__main__":
    print(json.dumps(executar(), ensure_ascii=False, indent=2))
