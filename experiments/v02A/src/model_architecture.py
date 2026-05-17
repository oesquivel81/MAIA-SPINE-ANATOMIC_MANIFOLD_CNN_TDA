
# ============================================================
# AUTO-GENERATED MODEL ARCHITECTURE
# ============================================================

import torch
import torch.nn as nn
import torch.nn.functional as F


class SmallUNetRegionAux(nn.Module):
    def __init__(self, *args, **kwargs):
        super().__init__()
        raise RuntimeError(
            "No se pudo auto-exportar SmallUNetRegionAux desde el notebook. "
            "Pega manualmente la clase SmallUNetRegionAux en model_architecture.py."
        )


# ============================================================
# BUILD MODEL HELPER
# ============================================================

MODEL_INIT_KWARGS_DEFAULT = {'in_channels': 2, 'base_ch': 32, 'num_region_classes': 25, 'dropout': 0.05}

def build_model(model_init_kwargs=None):
    if model_init_kwargs is None:
        model_init_kwargs = dict(MODEL_INIT_KWARGS_DEFAULT)

    return SmallUNetRegionAux(**model_init_kwargs)
