"""
FastBinaryCurveUNet — arquitectura CNN 1-canal para MAIA-SPINE.

Fuente: cuaderno de entrenamiento
  experiments/colab/PIPELINE_COMPLETE_2_CNN_OLD_SHARDS_...ipynb  bloque 12

Instanciación canónica:
    model = FastBinaryCurveUNet(in_channels=1, base_ch=24)

Entrada:  Tensor [B, 1, H, W]  float32  normalizado [0, 1]
Salida:   dict {"binary": Tensor[B,1,H,W], "curve": Tensor[B,1,H,W]}  (logits)
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class FastDoubleConv(nn.Module):
    """Bloque doble Conv-BN-ReLU, building block de encoder y decoder."""

    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class FastBinaryCurveUNet(nn.Module):
    """
    UNet simétrico de 3 niveles, 2 cabezas de salida (logits):
        - "binary" → máscara binaria de columna vertebral
        - "curve"  → línea media / curva de la columna

    Parámetros totales: ~1.25 M con base_ch=24.
    """

    def __init__(self, in_channels: int = 1, base_ch: int = 24) -> None:
        super().__init__()
        b = base_ch  # 24

        # ---- Encoder ----
        self.e1 = FastDoubleConv(in_channels, b)       # → 24
        self.e2 = FastDoubleConv(b, b * 2)             # → 48
        self.e3 = FastDoubleConv(b * 2, b * 4)         # → 96
        self.pool = nn.MaxPool2d(2)

        # ---- Bottleneck ----
        self.b = FastDoubleConv(b * 4, b * 8)          # → 192

        # ---- Decoder ----
        self.up3 = nn.ConvTranspose2d(b * 8, b * 4, kernel_size=2, stride=2)
        self.d3  = FastDoubleConv(b * 8, b * 4)        # cat(96+96)=192 → 96

        self.up2 = nn.ConvTranspose2d(b * 4, b * 2, kernel_size=2, stride=2)
        self.d2  = FastDoubleConv(b * 4, b * 2)        # cat(48+48)=96  → 48

        self.up1 = nn.ConvTranspose2d(b * 2, b, kernel_size=2, stride=2)
        self.d1  = FastDoubleConv(b * 2, b)            # cat(24+24)=48  → 24

        # ---- Cabezas de salida ----
        self.head_binary = nn.Conv2d(b, 1, kernel_size=1)
        self.head_curve  = nn.Conv2d(b, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        # Encoder
        s1 = self.e1(x)
        s2 = self.e2(self.pool(s1))
        s3 = self.e3(self.pool(s2))

        # Bottleneck
        bot = self.b(self.pool(s3))

        # Decoder con interpolate para tolerar size mismatch en H/W impares
        u3 = self.up3(bot)
        u3 = F.interpolate(u3, size=s3.shape[2:], mode="bilinear", align_corners=False)
        u3 = self.d3(torch.cat([u3, s3], dim=1))

        u2 = self.up2(u3)
        u2 = F.interpolate(u2, size=s2.shape[2:], mode="bilinear", align_corners=False)
        u2 = self.d2(torch.cat([u2, s2], dim=1))

        u1 = self.up1(u2)
        u1 = F.interpolate(u1, size=s1.shape[2:], mode="bilinear", align_corners=False)
        u1 = self.d1(torch.cat([u1, s1], dim=1))

        return {
            "binary": self.head_binary(u1),  # logits [B,1,H,W]
            "curve":  self.head_curve(u1),   # logits [B,1,H,W]
        }
