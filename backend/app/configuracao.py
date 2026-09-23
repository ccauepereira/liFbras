"""Environment configuration for the LiFbras API."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Configuracao:
    """Values needed to start the API in an environment."""

    ambiente: str
    origens_permitidas: tuple[str, ...]


def _ler_origens(valor: str | None) -> tuple[str, ...]:
    if not valor:
        return ("http://localhost:5173",)

    origens = tuple(origem.strip() for origem in valor.split(",") if origem.strip())
    return origens or ("http://localhost:5173",)


def carregar_configuracao() -> Configuracao:
    """Load the small set of runtime values from the process environment."""

    return Configuracao(
        ambiente=os.getenv("AMBIENTE", "desenvolvimento"),
        origens_permitidas=_ler_origens(os.getenv("ORIGENS_PERMITIDAS")),
    )
