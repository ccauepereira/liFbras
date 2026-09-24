from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parents[1]))

from modelo import BaselineMediaMLP, ReconhecedorGRU
from pose import DIMENSAO_MAOS_POSE, INDICES_POSE, combinar_maos_pose, extrair_pose_minima
from preprocessamento import preprocessar_maos_pose, preprocessar_sequencia, reamostrar_temporal
from treinar import criar_indices_divisao


def test_reamostragem_temporal_fixa_60_frames_para_comprimentos_variaveis():
    for comprimento in (1, 7, 60, 142):
        saida = reamostrar_temporal(np.ones((comprimento, 126), dtype=np.float32))
        assert saida.shape == (60, 126)


def test_preprocessamento_tem_shape_finitude_e_determinismo():
    origem = np.arange(8 * 126, dtype=np.float32).reshape(8, 126)
    primeiro = preprocessar_sequencia(origem, variante="wrist_scale")
    segundo = preprocessar_sequencia(origem, variante="wrist_scale")
    assert primeiro.shape == (60, 126)
    assert np.isfinite(primeiro).all()
    np.testing.assert_array_equal(primeiro, segundo)


def test_bloco_de_mao_ausente_permanece_zero():
    origem = np.zeros((12, 126), dtype=np.float32)
    origem[:, :63] = 1.0
    saida = preprocessar_sequencia(origem)
    assert np.all(saida[:, 63:] == 0)
    assert np.isfinite(saida).all()


def test_modelo_entrega_logits_batch_classes():
    modelo = ReconhecedorGRU(num_classes=5)
    logits = modelo(torch.zeros((3, 60, 126), dtype=torch.float32))
    assert logits.shape == (3, 5)
    assert torch.isfinite(logits).all()


def test_contrato_runtime_duas_maos_variavel_ate_logits():
    quadros = np.zeros((17, 126), dtype=np.float32)
    quadros[:, :63] = 0.25
    quadros[4:13, 63:] = 0.75
    tensor = torch.from_numpy(preprocessar_sequencia(quadros, variante="wrist_scale")).unsqueeze(0)
    logits = ReconhecedorGRU(num_classes=5)(tensor)
    assert tensor.shape == (1, 60, 126)
    assert torch.isfinite(tensor).all()
    assert logits.shape == (1, 5)


def test_mapeamento_de_classes_retorna_ao_caminho_da_fonte():
    pacote = np.load("dataset/libras-eqt-uece/mvp-hand-landmarks.npz", allow_pickle=False)
    nomes = pacote["label_names"].tolist()
    for label_id, origem in zip(pacote["label_ids"], pacote["source_files"]):
        assert Path(str(origem)).parts[-3] == nomes[int(label_id)]


def test_divisao_por_informante_separa_90_30_30_sem_vazamento():
    pacote = np.load("dataset/libras-eqt-uece/mvp-hand-landmarks.npz", allow_pickle=False)
    indices = criar_indices_divisao(pacote["signers"].astype(str))
    assert {nome: len(valores) for nome, valores in indices.items()} == {"treino": 90, "validacao": 30, "teste": 30}
    assert set(pacote["signers"][indices["treino"]]) == {"INFORMANTE 1", "INFORMANTE 2", "INFORMANTE 3"}
    assert set(pacote["signers"][indices["validacao"]]) == {"INFORMANTE 4"}
    assert set(pacote["signers"][indices["teste"]]) == {"INFORMANTE 5"}


def test_checkpoint_metadata_e_mapeamento_sao_legiveis():
    caminho = Path("ml/checkpoints/modelo_lifbras.pt")
    assert caminho.is_file()
    checkpoint = torch.load(caminho, map_location="cpu", weights_only=True)
    metadata = checkpoint["metadata"]
    assert metadata["input_size"] == 126
    assert metadata["sequence_length"] == 60
    assert list(metadata["class_to_index"]) == ["2_Sim", "7_Quero", "92_Energia", "110_Menos", "111_Mais"]


def test_extracao_pose_minima_preserva_os_indices_oficiais():
    holistic = np.arange(4 * 318, dtype=np.float32).reshape(4, 318)
    pose = extrair_pose_minima(holistic)
    esperado = holistic[:, :99].reshape(4, 33, 3)[:, INDICES_POSE].reshape(4, 15)
    assert pose.shape == (4, 15)
    np.testing.assert_array_equal(pose, esperado)


def test_combinacao_maos_pose_tem_141_valores_e_ordem_canonica():
    holistic = np.arange(3 * 318, dtype=np.float32).reshape(3, 318)
    maos = np.concatenate((holistic[:, 192:255], holistic[:, 255:318]), axis=1)
    combinado = combinar_maos_pose(maos, holistic)
    assert combinado.shape == (3, DIMENSAO_MAOS_POSE)
    np.testing.assert_array_equal(combinado[:, :126], maos)
    np.testing.assert_array_equal(combinado[:, 126:], extrair_pose_minima(holistic))


def test_preprocessamento_maos_pose_e_deterministico_finito_e_aceito_pela_mlp():
    origem = np.zeros((9, DIMENSAO_MAOS_POSE), dtype=np.float32)
    origem[:, :63] = 0.25
    origem[:, 63:126] = 0.5
    pose = origem[:, 126:].reshape(-1, 5, 3)
    pose[:, 0] = (0.5, 0.2, 0.0)
    pose[:, 1] = (0.35, 0.4, 0.0)
    pose[:, 2] = (0.65, 0.4, 0.0)
    pose[:, 3] = (0.25, 0.55, 0.0)
    pose[:, 4] = (0.75, 0.55, 0.0)
    primeiro = preprocessar_maos_pose(origem, "body_relative")
    segundo = preprocessar_maos_pose(origem, "body_relative")
    assert primeiro.shape == (60, DIMENSAO_MAOS_POSE)
    assert np.isfinite(primeiro).all()
    np.testing.assert_array_equal(primeiro, segundo)
    logits = BaselineMediaMLP(input_size=DIMENSAO_MAOS_POSE)(torch.from_numpy(primeiro).unsqueeze(0))
    assert logits.shape == (1, 5)


def test_pose_ausente_gera_componentes_corporais_zero_sem_nao_finitos():
    origem = np.ones((2, DIMENSAO_MAOS_POSE), dtype=np.float32)
    origem[:, 126:] = 0.0
    saida = preprocessar_maos_pose(origem, "body_relative")
    assert np.all(saida[:, 126:] == 0.0)
    assert np.all(saida[:, (0, 63)] == 0.0)
    assert np.isfinite(saida).all()
