"""Diagnose signer generalization without changing the LiFbras model contract."""

from __future__ import annotations

import io
import json
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

import matplotlib
matplotlib.use("Agg")
import numpy as np
import torch
from matplotlib import pyplot as plt
from torch import nn
from torch.utils.data import DataLoader

from modelo import BaselineMediaMLP, ReconhecedorGRU
from preprocessamento import DIMENSAO_ENTRADA, preprocessar_sequencia
from treinar import (
    ARQUIVO_DADOS,
    CAMINHO_RESULTADOS,
    CLASSES_ESPERADAS,
    SequenciasDataset,
    avaliar,
    carregar_dataset,
    criar_indices_divisao,
    fixar_semente,
    metricas,
    treinar_modelo,
)


RAIZ = Path(__file__).resolve().parents[1]
CAMINHO_GRU = RAIZ / "ml/checkpoints/modelo_lifbras.pt"
CAMINHO_MLP = RAIZ / "ml/checkpoints/modelo_lifbras_mlp.pt"
CAMINHO_DIAGNOSTICO = RAIZ / "ml/results/prompt08c-generalization.json"
PASTA_GRAFICOS = RAIZ / "ml/plots/generalization"
ARQUIVO_ZIP = RAIZ / "dataset/libras-eqt-uece/Landmarks.zip"
VARIANTE = "wrist_scale"
EPOCHS_MLP = 30
TAMANHO_BATCH = 16
SEMENTE = 42


def criar_loader(sequencias, labels, indices, shuffle: bool, seed: int, variante: str = VARIANTE) -> DataLoader:
    return DataLoader(
        SequenciasDataset(sequencias, labels, indices, variante),
        batch_size=TAMANHO_BATCH,
        shuffle=shuffle,
        generator=torch.Generator().manual_seed(seed) if shuffle else None,
    )


def avaliar_checkpoint_gru(sequencias, labels, signers, classes) -> dict:
    checkpoint = torch.load(CAMINHO_GRU, map_location="cpu", weights_only=True)
    metadata = checkpoint["metadata"]
    esperado = {classe: indice for indice, classe in enumerate(classes)}
    if metadata["class_to_index"] != esperado:
        raise ValueError("checkpoint class mapping differs from prepared dataset")
    if metadata["input_size"] != DIMENSAO_ENTRADA or metadata["sequence_length"] != 60:
        raise ValueError("checkpoint input contract differs from prepared dataset")
    if not metadata["preprocessing"].startswith(VARIANTE):
        raise ValueError("checkpoint preprocessing differs from diagnostic")
    indices = [indice for indice, signer in enumerate(signers) if signer == "INFORMANTE 5"]
    modelo = ReconhecedorGRU(metadata["input_size"], metadata["hidden_size"], len(classes))
    modelo.load_state_dict(checkpoint["state_dict"])
    modelo.eval()
    resultado = avaliar(modelo, criar_loader(sequencias, labels, indices, False, SEMENTE), len(classes), True)
    salvo = json.loads(CAMINHO_RESULTADOS.read_text(encoding="utf-8"))["test"]
    for chave in ("accuracy", "macro_precision", "macro_recall", "macro_f1", "loss"):
        if not np.isclose(resultado[chave], salvo[chave], atol=1e-12):
            raise ValueError(f"checkpoint reproduction changed {chave}: {resultado[chave]} != {salvo[chave]}")
    return {"metadata": metadata, "metrics": resultado, "test_signer": "INFORMANTE 5"}


def treinar_mlp_especificado(sequencias, labels, indices_train, indices_val, indices_test, classes) -> tuple[BaselineMediaMLP, dict]:
    """Replay the frozen 08B construction/training order without test evaluation."""
    fixar_semente(SEMENTE)
    loaders = {}
    for variante in ("raw", "wrist_scale"):
        loaders[variante] = {
            "treino": criar_loader(sequencias, labels, indices_train, True, SEMENTE, variante),
            "validacao": criar_loader(sequencias, labels, indices_val, False, SEMENTE, variante),
            "teste": criar_loader(sequencias, labels, indices_test, False, SEMENTE, variante),
        }
    treinar_modelo("reproduction_mlp_raw", BaselineMediaMLP(num_classes=len(classes)), loaders["raw"], EPOCHS_MLP, 1e-3, 1e-4, len(classes), SEMENTE)
    treinar_modelo("reproduction_gru_raw", ReconhecedorGRU(num_classes=len(classes)), loaders["raw"], EPOCHS_MLP, 1e-3, 1e-4, len(classes), SEMENTE)
    resultado = treinar_modelo("reproduction_mlp_wrist_scale", BaselineMediaMLP(num_classes=len(classes)), loaders["wrist_scale"], EPOCHS_MLP, 1e-3, 1e-4, len(classes), SEMENTE)
    return resultado["model"], {"history": resultado["history"], "validation": resultado["best_validation"]}


def resumo_array(valores: list[float]) -> dict:
    array = np.asarray(valores, dtype=np.float64)
    return {"mean": float(array.mean()), "median": float(np.median(array)), "min": float(array.min()), "max": float(array.max())}


def estatisticas_por_signer(sequencias, labels, signers, classes) -> dict:
    grupos = defaultdict(list)
    for sequencia, label, signer in zip(sequencias, labels, signers):
        grupos[(str(signer), classes[int(label)])].append(sequencia)
    resultado = {}
    for (signer, classe), amostras in sorted(grupos.items()):
        comprimentos, esquerda, direita, ambas, nenhuma, trajetorias, escalas = [], [], [], [], [], [], []
        faixas = []
        for sequencia in amostras:
            blocos = sequencia.reshape(-1, 2, 21, 3)
            presenca = np.any(blocos != 0, axis=(2, 3))
            comprimentos.append(sequencia.shape[0])
            esquerda.append(float(presenca[:, 0].mean()))
            direita.append(float(presenca[:, 1].mean()))
            ambas.append(float(presenca.all(axis=1).mean()))
            nenhuma.append(float((~presenca.any(axis=1)).mean()))
            ativos = sequencia[sequencia != 0]
            faixas.append((float(ativos.min()), float(ativos.max())))
            for bloco_indice in (0, 1):
                mao = blocos[:, bloco_indice]
                ativa = presenca[:, bloco_indice]
                if ativa.any():
                    pulsos = mao[ativa, 0]
                    trajetorias.append(float(np.linalg.norm(np.ptp(pulsos, axis=0))))
                    escala = np.linalg.norm(mao[ativa, 9] - mao[ativa, 0], axis=1)
                    escalas.extend(escala[escala > 1e-6].tolist())
        resultado[f"{signer} | {classe}"] = {
            "sequence_count": len(amostras),
            "length": resumo_array(comprimentos),
            "left_hand_frames_pct": 100 * float(np.mean(esquerda)),
            "right_hand_frames_pct": 100 * float(np.mean(direita)),
            "both_hands_frames_pct": 100 * float(np.mean(ambas)),
            "at_least_one_missing_hand_pct": 100 * float(1.0 - np.mean(ambas)),
            "no_hand_frames_pct": 100 * float(np.mean(nenhuma)),
            "coordinate_range": {"min": float(min(item[0] for item in faixas)), "max": float(max(item[1] for item in faixas))},
            "wrist_trajectory_range": resumo_array(trajetorias),
            "hand_scale": resumo_array(escalas),
        }
    return resultado


def verificar_blocos_holistic(source_files: list[str]) -> dict:
    direct, swapped, absent, max_errors = 0, 0, 0, []
    with ZipFile(ARQUIVO_ZIP) as archive:
        for source in source_files:
            holistic = source.replace("Libras-EQT-UECE (Hand Landmarks)", "Libras-EQT-UECE (Landmarks)")
            if holistic not in archive.namelist():
                absent += 1
                continue
            hands = np.load(io.BytesIO(archive.read(source)), allow_pickle=False)
            all_points = np.load(io.BytesIO(archive.read(holistic)), allow_pickle=False)
            if hands.shape[0] != all_points.shape[0]:
                absent += 1
                continue
            erro_direto = float(max(np.abs(hands[:, :63] - all_points[:, 192:255]).max(), np.abs(hands[:, 63:] - all_points[:, 255:318]).max()))
            erro_trocado = float(max(np.abs(hands[:, :63] - all_points[:, 255:318]).max(), np.abs(hands[:, 63:] - all_points[:, 192:255]).max()))
            max_errors.append(erro_direto)
            if np.isclose(erro_direto, 0.0):
                direct += 1
            elif np.isclose(erro_trocado, 0.0):
                swapped += 1
    return {
        "matched_files": direct,
        "swapped_files": swapped,
        "unmatched_or_missing_files": absent,
        "max_direct_error": float(max(max_errors)) if max_errors else None,
        "layout": "318 = pose[0:99] + reduced_face[99:192] + left_hand[192:255] + right_hand[255:318]",
    }


def criar_graficos(sequencias, labels, signers, classes, representacoes) -> None:
    PASTA_GRAFICOS.mkdir(parents=True, exist_ok=True)
    signers_alvo = ("INFORMANTE 1", "INFORMANTE 4", "INFORMANTE 5")
    indice_por_chave = {(classes[int(label)], str(signer)): indice for indice, (label, signer) in enumerate(zip(labels, signers))}
    figura, eixos = plt.subplots(len(classes), len(signers_alvo), figsize=(12, 17), constrained_layout=True)
    figura_escala, eixos_escala = plt.subplots(len(classes), len(signers_alvo), figsize=(12, 17), constrained_layout=True)
    for linha, classe in enumerate(classes):
        for coluna, signer in enumerate(signers_alvo):
            sequencia = sequencias[indice_por_chave[(classe, signer)]].reshape(-1, 2, 21, 3)
            eixo = eixos[linha, coluna]
            for bloco, nome, cor in ((0, "left wrist", "#0d9488"), (1, "right wrist", "#2563eb")):
                eixo.plot(sequencia[:, bloco, 0, 0], sequencia[:, bloco, 0, 1], color=cor, alpha=0.8, label=nome)
            eixo.plot(sequencia[:, 1, 8, 0], sequencia[:, 1, 8, 1], color="#d97706", alpha=0.65, label="right index tip")
            eixo.set_title(f"{classe} — {signer}", fontsize=8)
            eixo.invert_yaxis()
            if linha == 0 and coluna == 0:
                eixo.legend(fontsize=6)
            escala_eixo = eixos_escala[linha, coluna]
            for bloco, nome, cor in ((0, "left", "#0d9488"), (1, "right", "#2563eb")):
                escala = np.linalg.norm(sequencia[:, bloco, 9] - sequencia[:, bloco, 0], axis=1)
                escala_eixo.plot(np.linspace(0, 1, escala.size), escala, color=cor, label=nome)
            escala_eixo.set_title(f"{classe} — {signer}", fontsize=8)
            if linha == 0 and coluna == 0:
                escala_eixo.legend(fontsize=6)
    figura.savefig(PASTA_GRAFICOS / "trajectories_by_class_signer.png", dpi=160)
    figura_escala.savefig(PASTA_GRAFICOS / "hand_scale_by_class_signer.png", dpi=160)
    plt.close(figura)
    plt.close(figura_escala)

    vetores = representacoes
    centrados = vetores - vetores.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(centrados, full_matrices=False)
    projeção = centrados @ vt[:2].T
    cores = plt.get_cmap("tab10")
    for modo in ("class", "signer"):
        figura, eixo = plt.subplots(figsize=(8, 6), constrained_layout=True)
        grupos = classes if modo == "class" else sorted(set(signers.tolist()))
        for indice, grupo in enumerate(grupos):
            mascara = labels == indice if modo == "class" else signers == grupo
            eixo.scatter(projeção[mascara, 0], projeção[mascara, 1], s=30, color=cores(indice), label=grupo, alpha=0.8)
        eixo.set_title(f"PCA of wrist_scale temporal means by {modo}")
        eixo.set_xlabel("PC1")
        eixo.set_ylabel("PC2")
        eixo.legend(fontsize=8)
        figura.savefig(PASTA_GRAFICOS / f"pca_by_{modo}.png", dpi=160)
        plt.close(figura)


def analise_pca(representacoes: np.ndarray, labels: np.ndarray, signers: np.ndarray, classes: list[str]) -> dict:
    centrados = representacoes - representacoes.mean(axis=0, keepdims=True)
    _, singular, vt = np.linalg.svd(centrados, full_matrices=False)
    projeção = centrados @ vt[:2].T
    variancia = singular**2 / (representacoes.shape[0] - 1)
    explicada = variancia / variancia.sum()

    def distancias(mesmo):
        valores = []
        for indice in range(len(representacoes)):
            for outro in range(indice + 1, len(representacoes)):
                if mesmo(indice, outro):
                    valores.append(float(np.linalg.norm(representacoes[indice] - representacoes[outro])))
        return float(np.mean(valores))

    mesma_classe = distancias(lambda i, j: labels[i] == labels[j])
    classe_diferente = distancias(lambda i, j: labels[i] != labels[j])
    mesmo_signer = distancias(lambda i, j: signers[i] == signers[j])
    signer_diferente = distancias(lambda i, j: signers[i] != signers[j])
    # A lower within/between ratio means a more compact grouping.
    razao_classe = mesma_classe / classe_diferente
    razao_signer = mesmo_signer / signer_diferente
    return {
        "explained_variance_pc1_pc2": [float(explicada[0]), float(explicada[1])],
        "mean_distance_same_class": mesma_classe,
        "mean_distance_different_class": classe_diferente,
        "mean_distance_same_signer": mesmo_signer,
        "mean_distance_different_signer": signer_diferente,
        "class_compactness_ratio": razao_classe,
        "signer_compactness_ratio": razao_signer,
        "compactness_formula": "mean Euclidean distance within group / mean Euclidean distance between groups; lower is more compact",
        "projection_shape": list(projeção.shape),
    }


def descritores_temporais(sequencias) -> dict:
    meios, desvios, deslocamentos = [], [], []
    for sequencia in sequencias:
        processada = preprocessar_sequencia(sequencia, variante=VARIANTE)
        meios.append(processada.mean(axis=0))
        desvios.append(processada.std(axis=0))
        deslocamentos.append(processada[-1] - processada[0])
    return {"mean": np.asarray(meios), "std": np.asarray(desvios), "displacement": np.asarray(deslocamentos)}


def acuracia_centroide(treino, labels_treino, avaliacao, labels_avaliacao, classes) -> float:
    centroides = np.stack([treino[labels_treino == indice].mean(axis=0) for indice in range(len(classes))])
    previsoes = np.argmin(((avaliacao[:, None, :] - centroides[None, :, :]) ** 2).sum(axis=2), axis=1)
    return float(np.mean(previsoes == labels_avaliacao))


def rotacao_mlp(sequencias, labels, signers, classes) -> dict:
    resultado = {}
    for signer_teste in sorted(set(signers.tolist())):
        indices_treino = [indice for indice, signer in enumerate(signers) if signer != signer_teste]
        indices_teste = [indice for indice, signer in enumerate(signers) if signer == signer_teste]
        fixar_semente(SEMENTE)
        modelo = BaselineMediaMLP(num_classes=len(classes))
        loader = criar_loader(sequencias, labels, indices_treino, True, SEMENTE)
        criterio = nn.CrossEntropyLoss()
        otimizador = torch.optim.AdamW(modelo.parameters(), lr=1e-3, weight_decay=1e-4)
        for _ in range(EPOCHS_MLP):
            modelo.train()
            for entradas, rotulos in loader:
                otimizador.zero_grad(set_to_none=True)
                perda = criterio(modelo(entradas), rotulos)
                perda.backward()
                otimizador.step()
        resultado[signer_teste] = avaliar(modelo, criar_loader(sequencias, labels, indices_teste, False, SEMENTE), len(classes), True)
    return resultado


def executar() -> dict:
    torch.set_num_threads(1)
    sequencias, labels, signers, classes = carregar_dataset(ARQUIVO_DADOS)
    if classes != CLASSES_ESPERADAS:
        raise ValueError("prepared class order changed")
    indices = criar_indices_divisao(signers)
    reproducao_gru = avaliar_checkpoint_gru(sequencias, labels, signers, classes)

    mlp, reproducao_mlp = treinar_mlp_especificado(sequencias, labels, indices["treino"], indices["validacao"], indices["teste"], classes)
    salvo = json.loads(CAMINHO_RESULTADOS.read_text(encoding="utf-8"))
    if not np.isclose(reproducao_mlp["validation"]["macro_f1"], salvo["experiments"][2]["best_validation"]["macro_f1"], atol=1e-12):
        raise ValueError("frozen MLP validation result was not reproducible")
    teste_mlp = avaliar(mlp, criar_loader(sequencias, labels, indices["teste"], False, SEMENTE), len(classes), True)
    torch.save(
        {"state_dict": mlp.state_dict(), "metadata": {"model_type": "BaselineMediaMLP", "class_to_index": {classe: indice for indice, classe in enumerate(classes)}, "input_size": 126, "hidden_size": 64, "sequence_length": 60, "number_of_hands": 2, "preprocessing": "wrist_scale: linear temporal interpolation to 60 frames", "seed": SEMENTE}},
        CAMINHO_MLP,
    )

    representacoes = np.asarray([preprocessar_sequencia(sequencia, variante=VARIANTE).mean(axis=0) for sequencia in sequencias])
    distribuicoes = estatisticas_por_signer(sequencias, labels, signers, classes)
    blocos = verificar_blocos_holistic(np.load(ARQUIVO_DADOS, allow_pickle=False)["source_files"].tolist())
    criar_graficos(sequencias, labels, signers, classes, representacoes)
    pca = analise_pca(representacoes, labels, signers, classes)
    descritores = descritores_temporais(sequencias)
    descritor_centroides = {
        nome: {
            "validation_accuracy": acuracia_centroide(valor[indices["treino"]], labels[indices["treino"]], valor[indices["validacao"]], labels[indices["validacao"]], classes),
            "test_accuracy": acuracia_centroide(valor[indices["treino"]], labels[indices["treino"]], valor[indices["teste"]], labels[indices["teste"]], classes),
        }
        for nome, valor in descritores.items()
    }
    rotacao = rotacao_mlp(sequencias, labels, signers, classes)
    resultado = {
        "gru_checkpoint_reproduction": reproducao_gru,
        "mlp_audit": {"same_train_validation_split": True, "test_not_used_to_define_mlp": True, "preprocessing": "same wrist_scale [60,126] tensors; MLP adds temporal mean pooling only", "validation_reproduction": reproducao_mlp["validation"], "test_once": teste_mlp, "checkpoint": str(CAMINHO_MLP.relative_to(RAIZ))},
        "per_signer_class_distribution": distribuicoes,
        "hand_block_verification": blocos,
        "pca": pca,
        "temporal_descriptor_centroid_accuracy": descritor_centroides,
        "signer_rotation_mlp": rotacao,
        "plots": [str(path.relative_to(RAIZ)) for path in sorted(PASTA_GRAFICOS.glob("*.png"))],
    }
    CAMINHO_DIAGNOSTICO.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_DIAGNOSTICO.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


if __name__ == "__main__":
    print(json.dumps(executar(), ensure_ascii=False, indent=2))
