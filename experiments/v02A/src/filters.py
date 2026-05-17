
# ============================================================
# FILTERS FOR MAIA SPINE EXPERIMENT
# ============================================================

import numpy as np
import cv2

try:
    from skimage.filters import frangi
    from skimage.exposure import equalize_adapthist
except Exception:
    frangi = None
    equalize_adapthist = None


def normalize01_safe(x, eps=1e-8):
    x = np.asarray(x, dtype=np.float32)
    mn = float(np.nanmin(x))
    mx = float(np.nanmax(x))
    if mx - mn < eps:
        return np.zeros_like(x, dtype=np.float32)
    return np.clip((x - mn) / (mx - mn + eps), 0, 1).astype(np.float32)


def make_sobel_channel(img01):
    img = np.clip(np.asarray(img01, dtype=np.float32), 0, 1)
    gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
    return normalize01_safe(np.sqrt(gx ** 2 + gy ** 2))


def make_laplacian_channel(img01):
    img = np.clip(np.asarray(img01, dtype=np.float32), 0, 1)
    lap = cv2.Laplacian(img, cv2.CV_32F, ksize=3)
    return normalize01_safe(np.abs(lap))


def make_clahe_channel(img01):
    img = np.clip(np.asarray(img01, dtype=np.float32), 0, 1)
    u8 = (img * 255).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(u8).astype(np.float32) / 255.0


def make_canny_soft_channel(img01):
    img = np.clip(np.asarray(img01, dtype=np.float32), 0, 1)
    u8 = (img * 255).astype(np.uint8)
    edges = cv2.Canny(u8, 40, 120).astype(np.float32) / 255.0
    edges = cv2.GaussianBlur(edges, (3, 3), 0)
    return normalize01_safe(edges)


def make_highpass_soft_channel(img01):
    img = np.clip(np.asarray(img01, dtype=np.float32), 0, 1)
    blur = cv2.GaussianBlur(img, (0, 0), 6.0)
    hp = normalize01_safe(img - blur)
    hp = cv2.GaussianBlur(hp, (3, 3), 0.6)
    return normalize01_safe(hp)


class CombinedResponseV7Filter:
    def __init__(
        self,
        clahe_clip=0.02,
        denoise_h=9,
        lcn_sigma=7,
        frangi_weight=0.48,
        vertical_tophat_weight=0.25,
        lcn_weight=0.17,
        horizontal_penalty=-0.10,
        vertical_kernels=None,
        horizontal_kernels=None,
        frangi_sigmas=(1, 2, 3),
        black_ridges=False,
    ):
        self.clahe_clip = clahe_clip
        self.denoise_h = denoise_h
        self.lcn_sigma = lcn_sigma
        self.frangi_weight = frangi_weight
        self.vertical_tophat_weight = vertical_tophat_weight
        self.lcn_weight = lcn_weight
        self.horizontal_penalty = horizontal_penalty
        self.vertical_kernels = vertical_kernels or [(3, 15), (5, 25), (5, 35)]
        self.horizontal_kernels = horizontal_kernels or [(15, 3), (25, 5), (35, 5)]
        self.frangi_sigmas = frangi_sigmas
        self.black_ridges = black_ridges

    @staticmethod
    def _to_u8(img01):
        img01 = np.clip(np.asarray(img01, dtype=np.float32), 0, 1)
        return (img01 * 255).astype(np.uint8)

    def _preprocess_lcn(self, img01):
        if equalize_adapthist is None:
            raise ImportError("Falta scikit-image. Instala: pip install scikit-image")

        img01 = np.clip(np.asarray(img01, dtype=np.float32), 0, 1)

        clahe01 = equalize_adapthist(img01, clip_limit=self.clahe_clip)
        clahe_u8 = self._to_u8(clahe01)

        den_u8 = cv2.fastNlMeansDenoising(
            clahe_u8,
            None,
            h=self.denoise_h,
            templateWindowSize=7,
            searchWindowSize=21,
        )

        den01 = den_u8.astype(np.float32) / 255.0

        mean = cv2.GaussianBlur(den01, (0, 0), self.lcn_sigma)
        sqmean = cv2.GaussianBlur(den01 ** 2, (0, 0), self.lcn_sigma)
        std = np.sqrt(np.clip(sqmean - mean ** 2, 1e-6, None))

        lcn = np.clip((den01 - mean) / (std + 1e-3), -3, 3)
        return normalize01_safe(lcn)

    def _multiscale_tophat(self, image01, kernels):
        img_u8 = self._to_u8(normalize01_safe(image01))
        responses = []

        for kernel_size in kernels:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
            response = cv2.morphologyEx(img_u8, cv2.MORPH_TOPHAT, kernel)
            responses.append(response.astype(np.float32) / 255.0)

        return np.max(np.stack(responses, axis=0), axis=0).astype(np.float32)

    def __call__(self, img01):
        if frangi is None:
            raise ImportError("Falta scikit-image. Instala: pip install scikit-image")

        lcn01 = self._preprocess_lcn(img01)

        frangi_map = frangi(
            lcn01,
            sigmas=self.frangi_sigmas,
            black_ridges=self.black_ridges,
        )

        frangi_map = normalize01_safe(frangi_map)

        vertical_tophat = self._multiscale_tophat(lcn01, self.vertical_kernels)
        horizontal_tophat = self._multiscale_tophat(lcn01, self.horizontal_kernels)

        response = (
            self.frangi_weight * frangi_map
            + self.vertical_tophat_weight * vertical_tophat
            + self.lcn_weight * lcn01
            + self.horizontal_penalty * horizontal_tophat
        )

        response = np.clip(response, 0, None)
        return normalize01_safe(response).astype(np.float32)


_combined_v7 = CombinedResponseV7Filter()


def make_combined_v7_channel(img01):
    return _combined_v7(img01)


FILTER_FUNCS = {
    "sobel": make_sobel_channel,
    "laplacian": make_laplacian_channel,
    "clahe": make_clahe_channel,
    "canny_soft": make_canny_soft_channel,
    "highpass_soft": make_highpass_soft_channel,
    "combined_v7": make_combined_v7_channel,
}
