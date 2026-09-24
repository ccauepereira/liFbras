"""Small recurrent classifier used by the LiFbras baseline."""

from __future__ import annotations

import torch
from torch import nn


class ReconhecedorGRU(nn.Module):
    def __init__(self, input_size: int = 126, hidden_size: int = 64, num_classes: int = 5) -> None:
        super().__init__()
        self.gru = nn.GRU(input_size, hidden_size, num_layers=1, batch_first=True)
        self.classificador = nn.Linear(hidden_size, num_classes)

    def forward(self, sequencias: torch.Tensor) -> torch.Tensor:
        _, estado = self.gru(sequencias)
        return self.classificador(estado[-1])


class BaselineMediaMLP(nn.Module):
    """Lightweight ordering-discarding baseline for the temporal experiment."""

    def __init__(self, input_size: int = 126, hidden_size: int = 64, num_classes: int = 5) -> None:
        super().__init__()
        self.rede = nn.Sequential(nn.Linear(input_size, hidden_size), nn.ReLU(), nn.Linear(hidden_size, num_classes))

    def forward(self, sequencias: torch.Tensor) -> torch.Tensor:
        return self.rede(sequencias.mean(dim=1))
