"""
Arquitectura StudentUNet1CH4Heads.

Fuente: notebook PIPELINE_COMPLETE_2_CNN_OLD_SHARDS_REGIONIDX_FROM_YLABEL_FAST_20E_BS64 (8).ipynb
Bloque: 06_student_patch_cnn_1ch_4heads_from_teacher

Parámetros del checkpoint entrenado:
    model_name  : StudentUNet1CH4Heads
    base        : 16
    dropout     : 0.05
    input_ch    : 1
    img_size    : 224
    params      : 482 500
    outputs     : binary, boundary, intervertebral, ordinal
"""
from __future__ import annotations

import torch
import torch.nn as nn


class ConvBlockStudent(nn.Module):
    """Bloque doble Conv→BN→SiLU con Dropout2d opcional."""

    def __init__(self, in_ch: int, out_ch: int, dropout: float = 0.0) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.SiLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.SiLU(inplace=True),
        )
        self.drop: nn.Module = nn.Dropout2d(dropout) if dropout > 0 else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.drop(self.net(x))


class StudentUNet1CH4Heads(nn.Module):
    """
    UNet ligero de 3 niveles con 4 cabezas de salida independientes.

    input:  [B, 1, H, W]  float32  [0, 1]
    output: dict  →  4 tensores [B, 1, H, W] (logits; aplicar sigmoid para probabilidades):
        "binary"          — máscara binaria de la columna vertebral
        "boundary"        — bordes / límites intervertebrales
        "intervertebral"  — espacios intervertebrales
        "ordinal"         — clasificación ordinal (región / nivel vertebral)

    Encoder:
        e1 : ConvBlockStudent(1 → base)        + MaxPool
        e2 : ConvBlockStudent(base → base×2)   + MaxPool
        e3 : ConvBlockStudent(base×2 → base×4) + MaxPool
        b  : ConvBlockStudent(base×4 → base×8)  [bottleneck]

    Decoder (ConvTranspose2d + skip concat):
        d3 : ConvBlockStudent(base×8 → base×4)
        d2 : ConvBlockStudent(base×4 → base×2)
        d1 : ConvBlockStudent(base×2 → base)

    Cabezas (1×1 conv → logit):
        head_binary, head_boundary, head_intervertebral, head_ordinal
    """

    def __init__(self, base: int = 16, dropout: float = 0.05) -> None:
        super().__init__()

        # Encoder
        self.e1 = ConvBlockStudent(1, base, dropout=0.0)
        self.p1 = nn.MaxPool2d(2)

        self.e2 = ConvBlockStudent(base, base * 2, dropout=dropout)
        self.p2 = nn.MaxPool2d(2)

        self.e3 = ConvBlockStudent(base * 2, base * 4, dropout=dropout)
        self.p3 = nn.MaxPool2d(2)

        # Bottleneck
        self.b = ConvBlockStudent(base * 4, base * 8, dropout=dropout)

        # Decoder
        self.u3 = nn.ConvTranspose2d(base * 8, base * 4, kernel_size=2, stride=2)
        self.d3 = ConvBlockStudent(base * 8, base * 4, dropout=dropout)

        self.u2 = nn.ConvTranspose2d(base * 4, base * 2, kernel_size=2, stride=2)
        self.d2 = ConvBlockStudent(base * 4, base * 2, dropout=dropout)

        self.u1 = nn.ConvTranspose2d(base * 2, base, kernel_size=2, stride=2)
        self.d1 = ConvBlockStudent(base * 2, base, dropout=0.0)

        # Cabezas de salida (logits)
        self.head_binary = nn.Conv2d(base, 1, kernel_size=1)
        self.head_boundary = nn.Conv2d(base, 1, kernel_size=1)
        self.head_intervertebral = nn.Conv2d(base, 1, kernel_size=1)
        self.head_ordinal = nn.Conv2d(base, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        # Encoder
        e1 = self.e1(x)
        e2 = self.e2(self.p1(e1))
        e3 = self.e3(self.p2(e2))

        # Bottleneck
        b = self.b(self.p3(e3))

        # Decoder
        d3 = self.u3(b)
        d3 = torch.cat([d3, e3], dim=1)
        d3 = self.d3(d3)

        d2 = self.u2(d3)
        d2 = torch.cat([d2, e2], dim=1)
        d2 = self.d2(d2)

        d1 = self.u1(d2)
        d1 = torch.cat([d1, e1], dim=1)
        d1 = self.d1(d1)

        return {
            "binary": self.head_binary(d1),
            "boundary": self.head_boundary(d1),
            "intervertebral": self.head_intervertebral(d1),
            "ordinal": self.head_ordinal(d1),
        }
