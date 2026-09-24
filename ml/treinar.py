"""Train and evaluate the first LiFbras landmark sequence experiments."""

from __future__ import annotations

import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Iterable

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from modelo import BaselineMediaMLP, ReconhecedorGRU
from preprocessamento import DIMENSAO_ENTRADA, TAMANHO_TEMPORAL, preprocessar_sequencia


RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_DADOS = RAIZ / "dataset/libras-eqt-uece/mvp-hand-landmarks.npz"
CAMINHO_CHECKPOINT = RAIZ / "ml/checkpoints/modelo_lifbras.pt"
CAMINHO_RESULTADOS = RAIZ / "ml/results/prompt08b-results.json"
CLASSES_ESPERADAS = ["2_Sim", "7_Quero", "92_Energia", "110_Menos", "111_Mais"]
DIVISAO = {
    "treino": ("INFORMANTE 1", "INFORMANTE 2", "INFORMANTE 3"),
    "validacao": ("INFORMANTE 4",),
    "teste": ("INFORMANTE 5",),
}


def fixar_semente(semente: int) -> None:
    random.seed(semente)
    np.random.seed(semente)
    torch.manual_seed(semente)
    torch.use_deterministic_algorithms(True)


def carregar_dataset(caminho: Path) -> tuple[list[np.ndarray], np.ndarray, np.ndarray, list[str]]:
    pacote = np.load(caminho, allow_pickle=False)
    obrigatorios = {"features", "offsets", "label_ids", "label_names", "signers", "source_files"}
    ausentes = obrigatorios.difference(pacote.files)
    if ausentes:
        raise ValueError(f"prepared dataset missing fields: {sorted(ausentes)}")
    features = pacote["features"]
    offsets = pacote["offsets"]
    label_ids = pacote["label_ids"]
    label_names = pacote["label_names"].tolist()
    signers = pacote["signers"]
    source_files = pacote["source_files"].tolist()
    if features.dtype != np.float32 or features.ndim != 2 or features.shape[1] != DIMENSAO_ENTRADA:
        raise ValueError(f"features must be float32 [frames, 126], received {features.dtype} {features.shape}")
    if not np.isfinite(features).all():
        raise ValueError("prepared features contain NaN or Inf")
    if label_names != CLASSES_ESPERADAS:
        raise ValueError(f"class mapping changed: {label_names}")
    if offsets.ndim != 1 or offsets.size != label_ids.size + 1 or offsets[0] != 0 or offsets[-1] != features.shape[0]:
        raise ValueError("invalid sequence offsets")
    if signers.size != label_ids.size or not all(str(value) for value in signers.tolist()):
        raise ValueError("signer information is missing")
    sequencias = []
    for indice, (inicio, fim) in enumerate(zip(offsets[:-1], offsets[1:])):
        inicio, fim = int(inicio), int(fim)
        sequencia = features[inicio:fim]
        if sequencia.ndim != 2 or sequencia.shape[1] != DIMENSAO_ENTRADA or sequencia.shape[0] < 1:
            raise ValueError(f"invalid sequence {indice}: {sequencia.shape}")
        label_id = int(label_ids[indice])
        if not 0 <= label_id < len(label_names):
            raise ValueError(f"invalid label id at sequence {indice}")
        source_class = Path(str(source_files[indice])).parts[-3]
        source_signer = Path(str(source_files[indice])).parts[-2]
        if source_class != label_names[label_id] or source_signer != str(signers[indice]):
            raise ValueError(f"class/signer mapping mismatch at sequence {indice}")
        sequencias.append(sequencia.copy())
    return sequencias, label_ids.astype(np.int64), signers.astype(str), label_names


def estatisticas_dados(sequencias: list[np.ndarray], label_ids: np.ndarray, signers: np.ndarray, labels: list[str]) -> dict:
    comprimentos = np.asarray([sequencia.shape[0] for sequencia in sequencias])
    presenca = {label: {"left_only": 0, "right_only": 0, "both": 0, "zero": 0} for label in labels}
    for sequencia, label_id in zip(sequencias, label_ids):
        bloco = sequencia.reshape(-1, 2, 21, 3)
        maos = np.any(bloco != 0, axis=(2, 3))
        contador = presenca[labels[int(label_id)]]
        contador["left_only"] += int(np.sum(maos[:, 0] & ~maos[:, 1]))
        contador["right_only"] += int(np.sum(maos[:, 1] & ~maos[:, 0]))
        contador["both"] += int(np.sum(maos.all(axis=1)))
        contador["zero"] += int(np.sum(~maos.any(axis=1)))
    return {
        "samples": len(sequencias),
        "frames": int(comprimentos.sum()),
        "sequence_length": {"min": int(comprimentos.min()), "max": int(comprimentos.max()), "mean": float(comprimentos.mean())},
        "signers": dict(Counter(signers.tolist())),
        "class_counts": dict(Counter(labels[int(value)] for value in label_ids)),
        "hand_presence_frames": presenca,
    }


def criar_indices_divisao(signers: np.ndarray) -> dict[str, list[int]]:
    indices = {
        nome: [indice for indice, signer in enumerate(signers) if signer in informantes]
        for nome, informantes in DIVISAO.items()
    }
    tamanhos_esperados = {"treino": 90, "validacao": 30, "teste": 30}
    for nome, tamanho in tamanhos_esperados.items():
        if len(indices[nome]) != tamanho:
            raise ValueError(f"unexpected {nome} split size: {len(indices[nome])}")
    return indices


class SequenciasDataset(Dataset):
    def __init__(self, sequencias: list[np.ndarray], label_ids: np.ndarray, indices: Iterable[int], variante: str) -> None:
        self.sequencias = sequencias
        self.label_ids = label_ids
        self.indices = list(indices)
        self.variante = variante

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, indice: int) -> tuple[torch.Tensor, torch.Tensor]:
        original = self.indices[indice]
        array = preprocessar_sequencia(self.sequencias[original], variante=self.variante)
        return torch.from_numpy(array), torch.tensor(int(self.label_ids[original]), dtype=torch.long)


def metricas(y_true: list[int], y_pred: list[int], numero_classes: int) -> dict:
    matriz = np.zeros((numero_classes, numero_classes), dtype=np.int64)
    for verdadeiro, previsto in zip(y_true, y_pred):
        matriz[verdadeiro, previsto] += 1
    precisao, revocacao, f1 = [], [], []
    por_classe = []
    for classe in range(numero_classes):
        tp = int(matriz[classe, classe])
        fp = int(matriz[:, classe].sum() - tp)
        fn = int(matriz[classe, :].sum() - tp)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        precisao.append(p)
        revocacao.append(r)
        f1.append(f)
        por_classe.append({"precision": p, "recall": r, "f1": f, "support": int(matriz[classe].sum())})
    total = int(matriz.sum())
    return {
        "accuracy": float(np.trace(matriz) / total) if total else 0.0,
        "macro_precision": float(np.mean(precisao)),
        "macro_recall": float(np.mean(revocacao)),
        "macro_f1": float(np.mean(f1)),
        "per_class": por_classe,
        "confusion_matrix": matriz.tolist(),
    }


def avaliar(modelo: nn.Module, carregador: DataLoader, numero_classes: int, coletar_probabilidades: bool = False) -> dict:
    modelo.eval()
    perdas, y_true, y_pred, probabilidades, corretos = [], [], [], [], []
    criterio = nn.CrossEntropyLoss()
    with torch.no_grad():
        for sequencias, labels in carregador:
            logits = modelo(sequencias)
            perdas.append(float(criterio(logits, labels)))
            probs = torch.softmax(logits, dim=1)
            previsoes = logits.argmax(dim=1)
            y_true.extend(labels.tolist())
            y_pred.extend(previsoes.tolist())
            if coletar_probabilidades:
                probabilidades.extend(probs.max(dim=1).values.tolist())
                corretos.extend((previsoes == labels).tolist())
    resultado = metricas(y_true, y_pred, numero_classes)
    resultado["loss"] = float(np.mean(perdas))
    if coletar_probabilidades:
        resultado["max_probability"] = probabilidades
        resultado["correct"] = corretos
    return resultado


def treinar_modelo(
    nome: str,
    modelo: nn.Module,
    loaders: dict[str, DataLoader],
    epochs: int,
    learning_rate: float,
    weight_decay: float,
    numero_classes: int,
    seed: int,
) -> dict:
    criterio = nn.CrossEntropyLoss()
    otimizador = torch.optim.AdamW(modelo.parameters(), lr=learning_rate, weight_decay=weight_decay)
    historico = []
    melhor = None
    melhor_estado = None
    paciencia = 8
    sem_melhoria = 0
    gradiente_antes = None
    gradiente_depois = None
    for epoca in range(1, epochs + 1):
        modelo.train()
        perdas, y_true, y_pred = [], [], []
        for batch_index, (sequencias, labels) in enumerate(loaders["treino"]):
            otimizador.zero_grad(set_to_none=True)
            logits = modelo(sequencias)
            loss = criterio(logits, labels)
            if epoca == 1 and batch_index == 0:
                parametro = modelo.gru.weight_ih_l0 if hasattr(modelo, "gru") else modelo.rede[0].weight
                gradiente_antes = None if parametro.grad is None else float(parametro.grad.norm())
            loss.backward()
            if epoca == 1 and batch_index == 0:
                parametro = modelo.gru.weight_ih_l0 if hasattr(modelo, "gru") else modelo.rede[0].weight
                gradiente_depois = float(parametro.grad.norm())
            otimizador.step()
            perdas.append(float(loss.detach()))
            y_true.extend(labels.tolist())
            y_pred.extend(logits.argmax(dim=1).tolist())
        treino = metricas(y_true, y_pred, numero_classes)
        validacao = avaliar(modelo, loaders["validacao"], numero_classes)
        registro = {
            "epoch": epoca,
            "train_loss": float(np.mean(perdas)),
            "train_accuracy": treino["accuracy"],
            "validation_loss": validacao["loss"],
            "validation_accuracy": validacao["accuracy"],
            "validation_macro_f1": validacao["macro_f1"],
        }
        historico.append(registro)
        chave = (validacao["macro_f1"], -validacao["loss"])
        if melhor is None or chave > melhor:
            melhor = chave
            melhor_estado = {chave: valor.detach().clone() for chave, valor in modelo.state_dict().items()}
            sem_melhoria = 0
        else:
            sem_melhoria += 1
        print(f"{nome} epoch={epoca:02d} train_loss={registro['train_loss']:.4f} train_acc={registro['train_accuracy']:.3f} val_loss={registro['validation_loss']:.4f} val_acc={registro['validation_accuracy']:.3f} val_f1={registro['validation_macro_f1']:.3f}")
        if sem_melhoria >= paciencia:
            break
    assert melhor_estado is not None
    modelo.load_state_dict(melhor_estado)
    melhor_validacao = avaliar(modelo, loaders["validacao"], numero_classes, coletar_probabilidades=True)
    return {
        "name": nome,
        "model": modelo,
        "history": historico,
        "epochs_run": len(historico),
        "best_validation": melhor_validacao,
        "gradient_norm_before_backward": gradiente_antes,
        "gradient_norm_after_backward": gradiente_depois,
    }


def baseline_majoritario(label_ids: np.ndarray, indices_treino: list[int], indices_avaliacao: list[int], numero_classes: int) -> dict:
    contagem = Counter(int(label_ids[indice]) for indice in indices_treino)
    classe = min(contagem, key=lambda valor: (-contagem[valor], valor))
    return metricas([int(label_ids[indice]) for indice in indices_avaliacao], [classe] * len(indices_avaliacao), numero_classes) | {"class": classe}


def resumo_probabilidades(resultado: dict) -> dict:
    probs = np.asarray(resultado.get("max_probability", []), dtype=np.float64)
    corretos = np.asarray(resultado.get("correct", []), dtype=bool)
    resumo = {}
    for nome, mascara in (("correct", corretos), ("incorrect", ~corretos)):
        valores = probs[mascara]
        resumo[nome] = {"count": int(valores.size), "mean": float(valores.mean()) if valores.size else None, "min": float(valores.min()) if valores.size else None, "max": float(valores.max()) if valores.size else None}
    return resumo


def benchmark(modelo: nn.Module, sequencia: np.ndarray, variante: str) -> dict:
    modelo.eval()
    tempos_preprocessamento, tempos_forward = [], []
    with torch.no_grad():
        for _ in range(10):
            entrada = preprocessar_sequencia(sequencia, variante=variante)
            _ = modelo(torch.from_numpy(entrada).unsqueeze(0))
        for _ in range(200):
            inicio = time.perf_counter()
            entrada = preprocessar_sequencia(sequencia, variante=variante)
            tempos_preprocessamento.append((time.perf_counter() - inicio) * 1000)
            tensor = torch.from_numpy(entrada).unsqueeze(0)
            inicio = time.perf_counter()
            _ = modelo(tensor)
            tempos_forward.append((time.perf_counter() - inicio) * 1000)
    return {
        "label": "LOCAL DEVELOPMENT BENCHMARK",
        "preprocessing_median_ms": float(np.median(tempos_preprocessamento)),
        "preprocessing_p95_ms": float(np.percentile(tempos_preprocessamento, 95)),
        "forward_median_ms": float(np.median(tempos_forward)),
        "forward_p95_ms": float(np.percentile(tempos_forward, 95)),
    }


def executar(epochs: int = 30, batch_size: int = 16, seed: int = 42) -> dict:
    torch.set_num_threads(1)
    fixar_semente(seed)
    sequencias, label_ids, signers, labels = carregar_dataset(ARQUIVO_DADOS)
    estatisticas = estatisticas_dados(sequencias, label_ids, signers, labels)
    indices = criar_indices_divisao(signers)
    if any(not valores for valores in indices.values()):
        raise ValueError("one signer split is empty")
    for nome, valores in indices.items():
        if len(set(label_ids[valores].tolist())) != len(labels):
            raise ValueError(f"{nome} does not contain every class")
    print("dataset", json.dumps(estatisticas, ensure_ascii=False))
    print("split", {nome: len(valores) for nome, valores in indices.items()})
    for label_id, label in enumerate(labels):
        print("class_split", label, {nome: int(np.sum(label_ids[valores] == label_id)) for nome, valores in indices.items()}, estatisticas["hand_presence_frames"][label])

    loaders_por_variante = {}
    for variante in ("raw", "wrist_scale"):
        loaders_por_variante[variante] = {
            "treino": DataLoader(SequenciasDataset(sequencias, label_ids, indices["treino"], variante), batch_size=batch_size, shuffle=True, generator=torch.Generator().manual_seed(seed)),
            "validacao": DataLoader(SequenciasDataset(sequencias, label_ids, indices["validacao"], variante), batch_size=batch_size, shuffle=False),
            "teste": DataLoader(SequenciasDataset(sequencias, label_ids, indices["teste"], variante), batch_size=batch_size, shuffle=False),
        }

    maior_val = baseline_majoritario(label_ids, indices["treino"], indices["validacao"], len(labels))
    print("majority_validation", maior_val)
    experimentos = []
    for variante in ("raw", "wrist_scale"):
        loaders = loaders_por_variante[variante]
        mlp = treinar_modelo(f"mlp_{variante}", BaselineMediaMLP(num_classes=len(labels)), loaders, epochs, 1e-3, 1e-4, len(labels), seed)
        mlp["variant"] = variante
        mlp["kind"] = "mlp"
        experimentos.append(mlp)
        gru = treinar_modelo(f"gru_{variante}", ReconhecedorGRU(num_classes=len(labels)), loaders, epochs, 1e-3, 1e-4, len(labels), seed)
        gru["variant"] = variante
        gru["kind"] = "gru"
        experimentos.append(gru)
    grus = [experimento for experimento in experimentos if experimento["kind"] == "gru"]
    escolhido = max(grus, key=lambda experimento: (experimento["best_validation"]["macro_f1"], -experimento["best_validation"]["loss"]))
    modelo = escolhido["model"]
    variante = escolhido["variant"]
    sanity = preprocessar_sequencia(sequencias[indices["validacao"][0]], variante=variante)
    with torch.no_grad():
        logits_sanity = modelo(torch.from_numpy(sanity).unsqueeze(0))
        probs_sanity = torch.softmax(logits_sanity, dim=1)
    teste = avaliar(modelo, loaders_por_variante[variante]["teste"], len(labels), coletar_probabilidades=True)
    checkpoint = {
        "state_dict": modelo.state_dict(),
        "metadata": {
            "dataset_version": "LIBRAS-EQT-UECE v4",
            "dataset_doi": "10.5281/zenodo.21398895",
            "class_to_index": {label: indice for indice, label in enumerate(labels)},
            "input_size": DIMENSAO_ENTRADA,
            "hidden_size": 64,
            "sequence_length": TAMANHO_TEMPORAL,
            "number_of_hands": 2,
            "preprocessing": f"{variante}: linear temporal interpolation to 60 frames",
            "model_type": "ReconhecedorGRU",
            "seed": seed,
        },
    }
    CAMINHO_CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, CAMINHO_CHECKPOINT)
    parametro_gru = 3 * 64 * DIMENSAO_ENTRADA + 3 * 64 * 64 + 2 * 3 * 64
    parametro_linear = 64 * len(labels) + len(labels)
    manual_params = parametro_gru + parametro_linear
    pytorch_params = sum(parametro.numel() for parametro in modelo.parameters())
    resultados_experimentos = []
    for experimento in experimentos:
        resultados_experimentos.append({key: value for key, value in experimento.items() if key != "model"})
    resultado = {
        "config": {"seed": seed, "epochs_requested": epochs, "batch_size": batch_size, "learning_rate": 1e-3, "weight_decay": 1e-4, "sequence_length": TAMANHO_TEMPORAL, "input_size": DIMENSAO_ENTRADA, "split": DIVISAO},
        "dataset": estatisticas,
        "experiments": resultados_experimentos,
        "chosen": {"name": escolhido["name"], "variant": variante, "validation": escolhido["best_validation"], "epochs_run": escolhido["epochs_run"]},
        "majority_baseline_validation": maior_val,
        "chance_reference": 1 / len(labels),
        "sanity_check": {"sequence_shape": list(sanity.shape), "batch_shape": [1, *sanity.shape], "dtype": str(sanity.dtype), "label": labels[int(label_ids[indices["validacao"][0]])], "slice": sanity[:2, :6].tolist(), "logits": logits_sanity[0].tolist(), "probabilities": probs_sanity[0].tolist(), "predicted_index": int(logits_sanity.argmax()), "true_index": int(label_ids[indices["validacao"][0]])},
        "gradient_inspection": {"before_backward": escolhido["gradient_norm_before_backward"], "after_backward": escolhido["gradient_norm_after_backward"]},
        "manual_parameter_count": {"gru": parametro_gru, "linear": parametro_linear, "total": manual_params},
        "pytorch_parameter_count": pytorch_params,
        "test": teste,
        "validation_probability_summary": resumo_probabilidades(escolhido["best_validation"]),
        "test_probability_summary": resumo_probabilidades(teste),
        "latency": benchmark(modelo, sequencias[indices["validacao"][0]], variante),
        "checkpoint": {"path": str(CAMINHO_CHECKPOINT.relative_to(RAIZ)), "bytes": CAMINHO_CHECKPOINT.stat().st_size},
        "limitations": ["five-class closed vocabulary", "softmax is not calibrated certainty", "test signer is one local informant label", "browser PROMPT 09 must pack handedness into left/right 126-float blocks"],
    }
    CAMINHO_RESULTADOS.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_RESULTADOS.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


if __name__ == "__main__":
    executar()
