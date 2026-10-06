import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from ml.referencias_lifbras import (
    agrupar_por_signer, agrupar_por_sinal, carregar_referencias, carregar_referencias_completas,
    detectar_duplicatas, frame_array, resumo, split_por_signer, validar_schema,
)


def ref(signer="S001", ref_id="r1"):
    points = [{"x": .1, "y": .2, "z": .0} for _ in range(21)]
    return {"versao": 2, "referenciaId": ref_id, "tipo": "referencia_rotulada", "usarEmDataset": True, "sinalId": "7_Quero", "gloss": "Quero", "categoria": "experimental", "signerId": signer, "tentativa": 1, "criadoEm": "2026-10-05T00:00:00Z", "origem": "lifbras-camera", "referenciaDidatica": {"disponivel": True, "tipo": "video", "arquivo": "/referencia.mp4", "origem": "material didático do projeto"}, "validacao": {"status": "nao_validado"}, "captura": {"duracaoMs": 1000, "frames": [{"timestampMs": 0, "maoEsquerda": points, "maoDireita": None}]}}


def tecnico(ref_id="t1"):
    item = ref(ref_id=ref_id)
    item.update(tipo="teste_tecnico", usarEmDataset=False, sinalId=None, gloss=None, tentativa=None, categoria="debug_tecnico")
    item.pop("referenciaDidatica")
    return item


def test_schema_and_conversion_shape_absent_hand():
    item = ref(); validar_schema(item); array = frame_array(item)
    assert array.shape == (1, 2, 21, 3) and np.all(array[:, 1] == 0)


def test_invalid_version_and_class_rejected():
    item = ref(); item["versao"] = 3
    item["tipo"] = "invalid"
    with pytest.raises(ValueError): validar_schema(item)
    item = ref(); item["sinalId"] = "free_text"
    with pytest.raises(ValueError): validar_schema(item)


def test_grouping_duplicate_and_signer_split():
    refs = [ref("S001", "a"), ref("S001", "b"), ref("S002", "c")]
    refs[1]["captura"]["frames"][0]["maoEsquerda"][0]["x"] = .2
    refs[2]["captura"]["frames"][0]["maoEsquerda"][0]["x"] = .3
    assert len(agrupar_por_signer(refs)["S001"]) == 2
    assert len(agrupar_por_sinal(refs)["7_Quero"]) == 3
    assert detectar_duplicatas(refs) == []
    refs[1]["captura"]["frames"][0]["maoEsquerda"][0]["x"] = .1
    refs[1]["referenciaId"] = "b"; assert detectar_duplicatas(refs) == [["a", "b"]]
    train, test = split_por_signer(refs, "S002"); assert {x["signerId"] for x in train} == {"S001"}; assert {x["signerId"] for x in test} == {"S002"}


def test_json_loader_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "refs.json"; path.write_text(json.dumps([ref("S001", "a"), ref("S002", "a")]))
    with pytest.raises(ValueError): carregar_referencias(path)


def test_loader_excludes_technical_records_and_debug_summary_separates_them(tmp_path):
    path = tmp_path / "refs.json"; path.write_text(json.dumps([ref("S001", "labeled"), tecnico("technical")]))
    assert [item["tipo"] for item in carregar_referencias(path)] == ["referencia_rotulada"]
    complete = carregar_referencias_completas(path)
    stats = resumo(complete)
    assert stats["sequences"] == 1
    assert stats["technical_sequences"] == 1
    assert stats["by_sign"] == {"7_Quero": 1}


def test_technical_schema_allows_null_sign_but_rejects_inconsistent_dataset_flag():
    item = tecnico(); validar_schema(item)
    assert frame_array(item).shape == (1, 2, 21, 3)
    item["usarEmDataset"] = True
    with pytest.raises(ValueError): validar_schema(item)


def test_v1_import_is_explicitly_migrated(tmp_path):
    legacy = ref(ref_id="old"); legacy["versao"] = 1
    legacy.pop("tipo"); legacy.pop("usarEmDataset"); legacy.pop("referenciaDidatica")
    path = tmp_path / "legacy.json"; path.write_text(json.dumps([legacy]))
    loaded = carregar_referencias(path)
    assert loaded[0]["versao"] == 2
    assert loaded[0]["migradoDe"] == 1
    assert loaded[0]["tipo"] == "referencia_rotulada"


def test_labeled_schema_requires_sign_and_reference_source():
    item = ref(); item["sinalId"] = None
    with pytest.raises(ValueError): validar_schema(item)
    item = ref(); item.pop("referenciaDidatica")
    with pytest.raises(ValueError): validar_schema(item)
