"""FastAPI application entrypoint for LiFbras."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.configuracao import Configuracao, carregar_configuracao
from app.rotas.saude import roteador as roteador_saude


def criar_aplicacao(configuracao: Configuracao | None = None) -> FastAPI:
    configuracao = configuracao or carregar_configuracao()
    aplicacao = FastAPI(
        title="LiFbras API",
        description="API for the LiFbras educational application.",
        version="0.1.0",
    )
    aplicacao.add_middleware(
        CORSMiddleware,
        allow_origins=list(configuracao.origens_permitidas),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type"],
    )
    aplicacao.include_router(roteador_saude)
    return aplicacao


app = criar_aplicacao()
