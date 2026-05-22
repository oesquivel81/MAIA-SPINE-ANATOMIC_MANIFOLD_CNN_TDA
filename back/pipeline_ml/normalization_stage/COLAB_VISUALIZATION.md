# Colab Visualization Guide

Interactive visualization of normalized spine images in Google Colab and Jupyter notebooks.

## Overview

The `colab_visualization` module provides two main functions for displaying normalized spine images with optional patient metadata and comparison panels:

- **`display_normalized_image_in_colab()`** — Direct image display with flexible input options
- **`colab_display_normalization_result()`** — Convenience wrapper for pipeline result dictionaries

## Features

- ✅ Works in Google Colab and Jupyter notebooks
- ✅ Supports grayscale and color images
- ✅ Optional patient metadata in title (name, lastname, age)
- ✅ Graceful degradation if matplotlib not available
- ✅ Silent no-op when visualization disabled
- ✅ Loads images from numpy arrays or saved PNG files

## Usage

### Basic Example with Result Dictionary

After normalization pipeline completes, display the result:

```python
from pipeline_ml.normalization_stage import colab_display_normalization_result

# Assuming `result` comes from your normalization function
result = normalize_spine_image(patient_data)

colab_display_normalization_result(result, enable_visualization=True)
```

### Direct Image Array Display

```python
from pipeline_ml.normalization_stage import display_normalized_image_in_colab
import numpy as np

normalized_image = np.array(...)  # HxW or HxWxC array

display_normalized_image_in_colab(
    visualization_image=normalized_image,
    patient_name="Juan",
    patient_lastname="Perez",
    patient_age=42,
    enable_visualization=True
)
```

### Load from Saved File

```python
from pipeline_ml.normalization_stage import display_normalized_image_in_colab

display_normalized_image_in_colab(
    trace_visualization_path="/path/to/normalized.png",
    patient_name="Maria",
    enable_visualization=True
)
```

### Silent Execution (No Output)

```python
# With enable_visualization=False, display functions return silently
display_normalized_image_in_colab(
    visualization_image=normalized_array,
    enable_visualization=False  # No output, no warnings
)
```

## API Reference

### `display_normalized_image_in_colab()`

```python
def display_normalized_image_in_colab(
    visualization_image: Optional[np.ndarray] = None,
    trace_visualization_path: Optional[str] = None,
    patient_name: Optional[str] = None,
    patient_lastname: Optional[str] = None,
    patient_age: Optional[Union[int, str]] = None,
    enable_visualization: Optional[bool] = True,
) -> None
```

**Parameters:**

- `visualization_image` — numpy array (HxW or HxWxC). If None, loads from `trace_visualization_path`.
- `trace_visualization_path` — Path to PNG file. Used if `visualization_image` is None.
- `patient_name` — Optional first name for display in title.
- `patient_lastname` — Optional last name for display in title.
- `patient_age` — Optional age for display in title.
- `enable_visualization` — If False or None, silently returns (no-op). If True, displays.

**Behavior:**

- Converts grayscale to single-channel display with `cmap="gray"`
- Handles multi-channel images appropriately
- Warns if matplotlib/PIL not available
- Returns silently if no image data provided when `enable_visualization=True`

### `colab_display_normalization_result()`

```python
def colab_display_normalization_result(
    result: dict,
    enable_visualization: Optional[bool] = True,
) -> None
```

**Parameters:**

- `result` — Dictionary with normalization output (e.g., from pipeline function)
  - Expects keys: `visualization_image`, `trace_visualization_path`, `patient_name`, `patient_lastname`, `patient_age`
  - Optional: `enable_visualization` key in dict
- `enable_visualization` — Global override. If False, skips display.

**Behavior:**

- Extracts image and metadata from result dict
- Delegates to `display_normalized_image_in_colab()` for rendering
- Safe defaults if keys missing

## Integration with Pipeline

The visualization functions integrate with the normalization pipeline's trace artifact system:

```python
# In your Colab notebook after running normalization:
from pipeline_ml.normalization_stage import colab_display_normalization_result

result = pipeline.run(patient_data)
colab_display_normalization_result(result, enable_visualization=True)
```

## Requirements

- **Optional:** `matplotlib` (for display) — Install with `pip install matplotlib`
- **Optional:** `pillow` (for PNG loading) — Install with `pip install pillow`

If not installed, functions gracefully warn and return without error.

## Notes

- Visualization is **optional** — use `enable_visualization=False` to disable
- Function respects the pipeline's `enable_visualization` configuration flag
- No external dependencies required; matplotlib/PIL installed on-demand
- Colab/Jupyter focused; works in other Jupyter environments too
