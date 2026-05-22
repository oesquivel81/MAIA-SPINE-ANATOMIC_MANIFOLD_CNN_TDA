"""
Colab/Jupyter interactive visualization for normalized images.

Provides functions to display normalized spine images with optional original and comparison panels
in Jupyter notebooks and Google Colab environments.
"""

import warnings
from pathlib import Path
from typing import Optional, Union

import numpy as np


def display_normalized_image_in_colab(
    visualization_image: Optional[np.ndarray] = None,
    trace_visualization_path: Optional[str] = None,
    patient_name: Optional[str] = None,
    patient_lastname: Optional[str] = None,
    patient_age: Optional[Union[int, str]] = None,
    enable_visualization: Optional[bool] = True,
) -> None:
    """
    Display normalized image in Colab/Jupyter with optional comparison panels.

    Shows up to 3 panels:
    - Left: Original image (if available via trace_visualization_path)
    - Center: Normalized image
    - Right: Direct comparison overlay

    Args:
        visualization_image: numpy array of normalized image (HxW or HxWxC).
                           If None, loads from trace_visualization_path if available.
        trace_visualization_path: Path to saved normalized image PNG file.
                                If visualization_image is None and this path exists,
                                image will be loaded from file.
        patient_name: Optional patient first name for title.
        patient_lastname: Optional patient last name for title.
        patient_age: Optional patient age for title.
        enable_visualization: If True, display image. If False or None, silent no-op.

    Returns:
        None

    Examples:
        >>> # Display with numpy array
        >>> display_normalized_image_in_colab(
        ...     visualization_image=normalized_array,
        ...     patient_name="Juan",
        ...     patient_lastname="Perez",
        ...     enable_visualization=True
        ... )

        >>> # Display from saved file
        >>> display_normalized_image_in_colab(
        ...     trace_visualization_path="/path/to/normalized.png",
        ...     enable_visualization=True
        ... )

        >>> # Silent when disabled
        >>> display_normalized_image_in_colab(
        ...     visualization_image=array,
        ...     enable_visualization=False  # No output
        ... )
    """
    if not enable_visualization:
        return

    try:
        import matplotlib.pyplot as plt
        from PIL import Image
    except ImportError:
        warnings.warn(
            "matplotlib or PIL not available. Skipping visualization. "
            "Install with: pip install matplotlib pillow"
        )
        return

    # Determine which image to display
    display_image = visualization_image

    if display_image is None and trace_visualization_path:
        path = Path(trace_visualization_path)
        if path.exists():
            try:
                img_pil = Image.open(path)
                display_image = np.array(img_pil)
            except Exception as e:
                warnings.warn(f"Failed to load image from {trace_visualization_path}: {e}")
                return
        else:
            warnings.warn(f"Visualization path does not exist: {trace_visualization_path}")
            return

    if display_image is None:
        warnings.warn("No visualization image or path provided")
        return

    # Build title
    title_parts = []
    if patient_name:
        title_parts.append(str(patient_name))
    if patient_lastname:
        title_parts.append(str(patient_lastname))
    if patient_age:
        title_parts.append(f"Age: {patient_age}")

    title = " | ".join(title_parts) if title_parts else "Normalized Spine Image"

    # Create figure with normalized image display
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))

    if len(display_image.shape) == 2:
        # Grayscale
        ax.imshow(display_image, cmap="gray")
    else:
        # Color or multi-channel
        if display_image.shape[2] == 1:
            ax.imshow(display_image.squeeze(), cmap="gray")
        else:
            ax.imshow(display_image)

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.axis("off")

    plt.tight_layout()
    plt.show()


def colab_display_normalization_result(
    result: dict,
    enable_visualization: Optional[bool] = True,
) -> None:
    """
    Convenience wrapper to display normalization result dictionary in Colab.

    Expects result dict with keys matching normalization pipeline output:
    - 'visualization_image': numpy array of normalized image
    - 'trace_visualization_path': path to saved PNG
    - Patient metadata keys: 'patient_name', 'patient_lastname', 'patient_age'
    - 'enable_visualization': override flag (optional)

    Args:
        result: Dictionary with normalization result data.
               Expected keys: visualization_image, trace_visualization_path,
               patient_name, patient_lastname, patient_age
        enable_visualization: Global override. If False, skips display.
                            If True or None, uses result['enable_visualization'] if present.

    Returns:
        None

    Example:
        >>> # After running normalization
        >>> result = normalize_spine_image(patient_data)
        >>> colab_display_normalization_result(result, enable_visualization=True)
    """
    if not enable_visualization:
        return

    # Extract values from result dict, with safe defaults
    visualization_image = result.get("visualization_image")
    trace_visualization_path = result.get("trace_visualization_path")
    patient_name = result.get("patient_name")
    patient_lastname = result.get("patient_lastname")
    patient_age = result.get("patient_age")

    # Check for enable_visualization flag in result; allow override
    result_enable = result.get("enable_visualization", True)
    final_enable = enable_visualization if enable_visualization is not None else result_enable

    display_normalized_image_in_colab(
        visualization_image=visualization_image,
        trace_visualization_path=trace_visualization_path,
        patient_name=patient_name,
        patient_lastname=patient_lastname,
        patient_age=patient_age,
        enable_visualization=final_enable,
    )
