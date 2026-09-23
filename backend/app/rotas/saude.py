"""Health endpoint for the LiFbras API."""

from fastapi import APIRouter
from pydantic import BaseModel


class RespostaSaude(BaseModel):
    status: str


roteador = APIRouter(prefix="/api/v1", tags=["saude"])


@roteador.get("/saude", response_model=RespostaSaude)
def verificar_saude() -> RespostaSaude:
    return RespostaSaude(status="ok")
