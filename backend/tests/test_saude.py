from fastapi.testclient import TestClient

from app.configuracao import Configuracao, carregar_configuracao
from app.main import criar_aplicacao


def test_aplicacao_inicia_e_expoe_saude() -> None:
    cliente = TestClient(criar_aplicacao())

    resposta = cliente.get("/api/v1/saude")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_cors_permite_origem_configurada() -> None:
    configuracao = Configuracao(
        ambiente="teste",
        origens_permitidas=("http://localhost:4173",),
    )
    cliente = TestClient(criar_aplicacao(configuracao))

    resposta = cliente.get(
        "/api/v1/saude",
        headers={"Origin": "http://localhost:4173"},
    )

    assert resposta.status_code == 200
    assert resposta.headers["access-control-allow-origin"] == "http://localhost:4173"


def test_cors_nao_permite_origem_desconhecida() -> None:
    configuracao = Configuracao(
        ambiente="teste",
        origens_permitidas=("http://localhost:4173",),
    )
    cliente = TestClient(criar_aplicacao(configuracao))

    resposta = cliente.get(
        "/api/v1/saude",
        headers={"Origin": "https://exemplo.invalid"},
    )

    assert resposta.status_code == 200
    assert "access-control-allow-origin" not in resposta.headers


def test_configuracao_le_origens_do_ambiente(monkeypatch) -> None:
    monkeypatch.setenv("AMBIENTE", "producao")
    monkeypatch.setenv(
        "ORIGENS_PERMITIDAS",
        "https://lifbras.example, https://www.lifbras.example",
    )

    configuracao = carregar_configuracao()

    assert configuracao.ambiente == "producao"
    assert configuracao.origens_permitidas == (
        "https://lifbras.example",
        "https://www.lifbras.example",
    )
