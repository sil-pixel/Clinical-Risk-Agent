"""Inference-only DCMFNet architecture from the authoritative Thesis runtime.

Source revision: Thesis repository commit
``2f6d96db481873fce8a3ba35f29d6e4ee5359dd9``.
"""

from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import Tensor, nn


class GatedModule(nn.Module):
    """Update a modality representation with a learned feature gate."""

    def __init__(self, n_features_m: int) -> None:
        super().__init__()
        self.W_update = nn.Linear(n_features_m, n_features_m)
        self.W_gate = nn.Linear(2 * n_features_m, n_features_m)

    def forward(self, F_curr: Tensor, G_prev: Tensor) -> Tensor:
        update = torch.sigmoid(self.W_update(F_curr + G_prev))
        gated = F_curr * update
        return torch.tanh(self.W_gate(torch.cat((F_curr, gated), dim=1)))


class FusionModule(nn.Module):
    """Bilinearly fuse the anchor and current modality representations."""

    def __init__(self, n_features_x: int, n_features_m: int) -> None:
        super().__init__()
        self.W1 = nn.Linear(n_features_x, n_features_m)
        self.W2 = nn.Linear(n_features_m, n_features_m)

    def forward(self, X: Tensor, G_prev: Tensor) -> Tensor:
        return torch.tanh(torch.tanh(self.W1(X)) * torch.tanh(self.W2(G_prev)))


class GatedFusionLayer(nn.Module):
    """One fusion step followed by a gated representation update."""

    def __init__(self, n_features_x: int, n_features_m: int) -> None:
        super().__init__()
        self.fusion_layer = FusionModule(n_features_x, n_features_m)
        self.gated_layer = GatedModule(n_features_m)

    def forward(self, X: Tensor, G_prev: Tensor) -> tuple[Tensor, Tensor]:
        fused = self.fusion_layer(X, G_prev)
        return fused, self.gated_layer(fused, G_prev)


class SEAttention(nn.Module):
    """Squeeze-and-excitation feature recalibration for tabular tensors."""

    def __init__(
        self,
        n_features: int,
        se_reduction: int = 2,
        dropout: float = 0.3,
        hidden_dim_min: int = 8,
    ) -> None:
        super().__init__()
        if n_features <= 0:
            raise ValueError("n_features must be positive")
        if se_reduction <= 0:
            raise ValueError("se_reduction must be positive")
        if not 0.0 <= dropout < 1.0:
            raise ValueError("dropout must be in [0, 1)")
        hidden_dim = max(n_features // se_reduction, hidden_dim_min)
        self.excitation = nn.Sequential(
            nn.Linear(n_features, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, n_features),
            nn.Sigmoid(),
        )

    def forward(self, inputs: Tensor) -> Tensor:
        return inputs * self.excitation(inputs)


class IterativeGatedFusionModule(nn.Module):
    """Repeatedly fuse one modality with the anchor modality."""

    def __init__(
        self,
        L: int,
        n_features_x: int,
        n_features_m: int,
        se_reduction: int = 2,
        dropout: float = 0.3,
        hidden_dim_min: int = 8,
    ) -> None:
        super().__init__()
        if L <= 0:
            raise ValueError("L must be positive")
        self.L = L
        self.gated_fusion_layers = nn.ModuleList(
            GatedFusionLayer(n_features_x, n_features_m) for _ in range(L)
        )
        self.attention = SEAttention(
            n_features_m * L,
            se_reduction=se_reduction,
            dropout=dropout,
            hidden_dim_min=hidden_dim_min,
        )

    def forward(self, X: Tensor, X_modality: Tensor) -> Tensor:
        previous = X_modality
        fused_outputs: list[Tensor] = []
        for layer in self.gated_fusion_layers:
            fused, previous = layer(X, previous)
            fused_outputs.append(fused)
        return self.attention(torch.cat(fused_outputs, dim=1))


class DeepCrossModalFusionModel(nn.Module):
    """DCMFNet regression model for normalized symptom-severity targets."""

    def __init__(
        self,
        M: int,
        L: int | Sequence[int],
        n_features_per_modality: Sequence[int],
        se_reduction: int = 2,
        dropout: float = 0.3,
        hidden_dim_min: int = 8,
    ) -> None:
        super().__init__()
        if M <= 0:
            raise ValueError("M must be positive")
        feature_sizes = [int(size) for size in n_features_per_modality]
        if len(feature_sizes) != M + 2:
            raise ValueError(
                "n_features_per_modality must contain the anchor modality, "
                f"{M} fusion modalities, and one independent modality"
            )
        if any(size <= 0 for size in feature_sizes):
            raise ValueError("All feature sizes must be positive")

        self.M = M
        if isinstance(L, int):
            self.layers_per_modality = [L] * M
        else:
            self.layers_per_modality = [int(depth) for depth in L]
            if len(self.layers_per_modality) != M:
                raise ValueError(f"L must contain {M} layer counts")
        if any(depth <= 0 for depth in self.layers_per_modality):
            raise ValueError("All layer counts must be positive")

        anchor_size = feature_sizes[0]
        fusion_sizes = feature_sizes[1 : M + 1]
        self.igf_modules = nn.ModuleList(
            IterativeGatedFusionModule(
                self.layers_per_modality[index],
                anchor_size,
                fusion_sizes[index],
                se_reduction=se_reduction,
                dropout=dropout,
                hidden_dim_min=hidden_dim_min,
            )
            for index in range(M)
        )

        fused_dim = sum(
            depth * size
            for depth, size in zip(
                self.layers_per_modality, fusion_sizes, strict=True
            )
        )
        independent_dim = sum(feature_sizes)
        final_dim = fused_dim + independent_dim
        self.attn_fused = SEAttention(
            fused_dim, se_reduction, dropout, hidden_dim_min
        )
        self.attn_independent = SEAttention(
            independent_dim, se_reduction, dropout, hidden_dim_min
        )
        self.attn_final = SEAttention(
            final_dim, se_reduction, dropout, hidden_dim_min
        )
        self.fc = nn.Linear(final_dim, 1)

    def forward(self, inputs: Sequence[Tensor]) -> Tensor:
        if len(inputs) != self.M + 2:
            raise ValueError(f"Expected {self.M + 2} modality tensors")
        anchor = inputs[0]
        modalities = inputs[1 : self.M + 1]

        fused = self.attn_fused(
            torch.cat(
                [
                    module(anchor, modality)
                    for module, modality in zip(
                        self.igf_modules, modalities, strict=True
                    )
                ],
                dim=-1,
            )
        )
        raw_modalities = self.attn_independent(torch.cat(list(inputs), dim=-1))
        return self.fc(self.attn_final(torch.cat((fused, raw_modalities), dim=-1)))


DCMFNet = DeepCrossModalFusionModel

__all__ = ["DCMFNet", "DeepCrossModalFusionModel"]
