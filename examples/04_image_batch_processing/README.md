# Image Batch Processing

This example demonstrates **batch image processing** with resource-aware scheduling, showing how Lattice can manage CPU (and GPU) resources for image operations.

## Overview

Image processing pipelines typically involve:
1. **Resize** images to target dimensions
2. **Apply filters** (blur, sharpen, etc.)
3. **Combine** into final output (gallery, sprite sheet, etc.)

```
    ┌────┬────┬────┬────┐
    ↓    ↓    ↓    ↓
   R0   R1   R2   R3   ← Parallel resize (1s each)
    ↓    ↓    ↓    ↓
   F0   F1   F2   F3   ← Parallel filter (1.5s each)
    ↓    ↓    ↓    ↓
    └────┴────┴────┴────┘
              ↓
         Gallery (1s)
```

## Performance

| Execution Mode | Time | Speedup |
|----------------|------|---------|
| Sequential | ~11s | 1.0x |
| Lattice Parallel | ~3.5s | **3.1x** |

## Requirements

- **Optional:** Pillow (`pip install Pillow`) for real image processing
- Works without Pillow using mock images

## Usage

1. Start Lattice server:
   ```bash
   lattice start --head --port 8000
   ```

2. (Optional) Install Pillow:
   ```bash
   pip install Pillow
   ```

3. Run the example:
   ```bash
   python main.py
   ```

## What It Does

1. **Creates** 4 sample images (different sizes and colors)
2. **Resizes** all images to 400x300 in parallel
3. **Applies** different filters (blur, sharpen, contour, emboss) in parallel
4. **Generates** a gallery summary

## Resource Requirements

Each task specifies its resource needs:

```python
@task(
    inputs=["image_data", "image_id"],
    outputs=["processed_image"],
    resources={"cpu": 2, "cpu_mem": 512}  # 2 CPU cores, 512MB RAM
)
def process_image(params):
    ...
```

For GPU processing (e.g., AI upscaling), you could specify:
```python
resources={"cpu": 1, "gpu": 1, "gpu_mem": 4096}  # 1 GPU, 4GB VRAM
```

## Real-World Applications

- **Thumbnail generation** - Process uploaded images in parallel
- **Video processing** - Extract and process frames in parallel
- **ML preprocessing** - Prepare training images with augmentation
- **Photo editing** - Batch apply filters to albums
