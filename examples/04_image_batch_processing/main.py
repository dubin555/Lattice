"""
Image Batch Processing - Demonstrates CPU/GPU Resource Management
==================================================================

This example shows how Lattice handles batch image processing with
different resource requirements for different operations.

Workflow Structure:
    Input Images (4 images)
         ↓
    ┌────┬────┬────┬────┐
    ↓    ↓    ↓    ↓
  Resize Resize Resize Resize  ← CPU tasks (1s each)
    ↓    ↓    ↓    ↓
 Filter Filter Filter Filter   ← CPU tasks (1.5s each)
    ↓    ↓    ↓    ↓
    └────┴────┴────┴────┘
              ↓
    Combine into Gallery

Performance:
    - Sequential: 4×1 + 4×1.5 + 1 = 11 seconds
    - Lattice Parallel: 1 + 1.5 + 1 = 3.5 seconds (3.1x speedup)

Requirements: Pillow (pip install Pillow)

Usage:
    1. Start Lattice server: lattice start --head --port 8000
    2. Run this script: python main.py
"""

import time
import os
import io
import base64
from lattice import LatticeClient, task

HAS_PIL = False
try:
    from PIL import Image, ImageFilter, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    pass


def create_sample_image(width, height, color, text):
    """Create a simple sample image for demo purposes."""
    if not HAS_PIL:
        return {
            "width": width,
            "height": height,
            "color": color,
            "text": text,
            "mock": True
        }
    
    img = Image.new('RGB', (width, height), color)
    draw = ImageDraw.Draw(img)
    
    text_bbox = draw.textbbox((0, 0), text)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    draw.text((x, y), text, fill='white')
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


@task(
    inputs=["image_data", "image_id", "target_width", "target_height"],
    outputs=["resized_image", "original_size", "new_size"],
    resources={"cpu": 2, "cpu_mem": 512}
)
def resize_image(params):
    """
    Resize an image to target dimensions.
    CPU-bound task.
    """
    image_data = params.get("image_data")
    image_id = params.get("image_id")
    target_width = params.get("target_width")
    target_height = params.get("target_height")
    
    print(f"[Resize {image_id}] Resizing to {target_width}x{target_height}...")
    
    time.sleep(1)
    
    if isinstance(image_data, dict) and image_data.get("mock"):
        original_size = f"{image_data['width']}x{image_data['height']}"
        new_size = f"{target_width}x{target_height}"
        resized = {
            "width": target_width,
            "height": target_height,
            "color": image_data["color"],
            "text": image_data["text"],
            "mock": True
        }
    elif HAS_PIL:
        img_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(img_bytes))
        original_size = f"{img.width}x{img.height}"
        
        img_resized = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        new_size = f"{target_width}x{target_height}"
        
        buffer = io.BytesIO()
        img_resized.save(buffer, format='PNG')
        resized = base64.b64encode(buffer.getvalue()).decode('utf-8')
    else:
        original_size = "unknown"
        new_size = f"{target_width}x{target_height}"
        resized = image_data
    
    print(f"[Resize {image_id}] ✓ Resized: {original_size} → {new_size}")
    
    return {
        "resized_image": resized,
        "original_size": original_size,
        "new_size": new_size
    }


@task(
    inputs=["image_data", "image_id", "filter_type"],
    outputs=["filtered_image", "filter_applied"],
    resources={"cpu": 2, "cpu_mem": 512}
)
def apply_filter(params):
    """
    Apply image filter (blur, sharpen, etc.).
    CPU-bound task.
    """
    image_data = params.get("image_data")
    image_id = params.get("image_id")
    filter_type = params.get("filter_type")
    
    print(f"[Filter {image_id}] Applying {filter_type} filter...")
    
    time.sleep(1.5)
    
    if isinstance(image_data, dict) and image_data.get("mock"):
        filtered = image_data.copy()
        filtered["filter"] = filter_type
    elif HAS_PIL:
        img_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(img_bytes))
        
        filter_map = {
            "blur": ImageFilter.GaussianBlur(radius=2),
            "sharpen": ImageFilter.SHARPEN,
            "contour": ImageFilter.CONTOUR,
            "emboss": ImageFilter.EMBOSS,
        }
        
        if filter_type in filter_map:
            img_filtered = img.filter(filter_map[filter_type])
        else:
            img_filtered = img
        
        buffer = io.BytesIO()
        img_filtered.save(buffer, format='PNG')
        filtered = base64.b64encode(buffer.getvalue()).decode('utf-8')
    else:
        filtered = image_data
    
    print(f"[Filter {image_id}] ✓ Applied {filter_type} filter")
    
    return {
        "filtered_image": filtered,
        "filter_applied": filter_type
    }


@task(
    inputs=["image_0", "image_1", "image_2", "image_3",
            "size_0", "size_1", "size_2", "size_3",
            "filter_0", "filter_1", "filter_2", "filter_3"],
    outputs=["gallery_summary", "output_dir"],
    resources={"cpu": 1, "cpu_mem": 256}
)
def create_gallery(params):
    """
    Combine all processed images into a gallery.
    """
    print(f"[Gallery] Creating image gallery...")
    
    time.sleep(1)
    
    summary = {
        "images_processed": 4,
        "images": []
    }
    
    for i in range(4):
        img_info = {
            "id": i,
            "size": params.get(f"size_{i}"),
            "filter": params.get(f"filter_{i}"),
        }
        summary["images"].append(img_info)
    
    output_dir = os.path.join(os.getcwd(), "output_gallery")
    
    print(f"[Gallery] ✓ Gallery created with {summary['images_processed']} images")
    
    return {
        "gallery_summary": summary,
        "output_dir": output_dir
    }


def main():
    print("=" * 60)
    print("🖼️  Lattice Image Batch Processing Demo")
    print("=" * 60)
    
    if not HAS_PIL:
        print("""
⚠️  Pillow not installed - using mock image processing.
    Install Pillow for real image processing: pip install Pillow
        """)
    
    print("""
This demo shows how Lattice parallelizes image batch processing
with multiple stages: resize → filter → combine.
    """)
    
    sample_images = [
        create_sample_image(800, 600, (255, 100, 100), "Image 1"),
        create_sample_image(1024, 768, (100, 255, 100), "Image 2"),
        create_sample_image(640, 480, (100, 100, 255), "Image 3"),
        create_sample_image(1280, 720, (255, 255, 100), "Image 4"),
    ]
    
    filters = ["blur", "sharpen", "contour", "emboss"]
    
    print(f"\n📁 Processing {len(sample_images)} images")
    print(f"   Filters to apply: {', '.join(filters)}")
    
    print("\n" + "=" * 60)
    print("Running with LATTICE parallel execution...")
    print("=" * 60)
    
    start_time = time.time()
    
    client = LatticeClient("http://localhost:8000")
    workflow = client.create_workflow()
    
    resize_tasks = []
    for i, img in enumerate(sample_images):
        resize_task = workflow.add_task(
            resize_image,
            inputs={
                "image_data": img,
                "image_id": i,
                "target_width": 400,
                "target_height": 300
            },
            task_name=f"resize_{i}"
        )
        resize_tasks.append(resize_task)
    
    filter_tasks = []
    for i, (resize_task, filter_type) in enumerate(zip(resize_tasks, filters)):
        filter_task = workflow.add_task(
            apply_filter,
            inputs={
                "image_data": resize_task.outputs["resized_image"],
                "image_id": i,
                "filter_type": filter_type
            },
            task_name=f"filter_{i}"
        )
        filter_tasks.append(filter_task)
    
    gallery_task = workflow.add_task(
        create_gallery,
        inputs={
            "image_0": filter_tasks[0].outputs["filtered_image"],
            "image_1": filter_tasks[1].outputs["filtered_image"],
            "image_2": filter_tasks[2].outputs["filtered_image"],
            "image_3": filter_tasks[3].outputs["filtered_image"],
            "size_0": resize_tasks[0].outputs["new_size"],
            "size_1": resize_tasks[1].outputs["new_size"],
            "size_2": resize_tasks[2].outputs["new_size"],
            "size_3": resize_tasks[3].outputs["new_size"],
            "filter_0": filter_tasks[0].outputs["filter_applied"],
            "filter_1": filter_tasks[1].outputs["filter_applied"],
            "filter_2": filter_tasks[2].outputs["filter_applied"],
            "filter_3": filter_tasks[3].outputs["filter_applied"],
        }
    )
    
    print("\n📊 Workflow Structure:")
    print("    ┌────┬────┬────┬────┐")
    print("    ↓    ↓    ↓    ↓")
    print("   R0   R1   R2   R3   ← Parallel resize (CPU)")
    print("    ↓    ↓    ↓    ↓")
    print("   F0   F1   F2   F3   ← Parallel filter (CPU)")
    print("    ↓    ↓    ↓    ↓")
    print("    └────┴────┴────┴────┘")
    print("              ↓")
    print("         Gallery")
    print()
    
    run_id = workflow.run()
    results = workflow.get_results(run_id, verbose=False)
    
    elapsed = time.time() - start_time
    
    for msg in results:
        if msg.get("type") == "task_complete":
            output = msg.get("output", {})
            if "gallery_summary" in output:
                summary = output["gallery_summary"]
                print("\n📋 Gallery Summary:")
                print(f"   Images Processed: {summary['images_processed']}")
                for img in summary["images"]:
                    print(f"   - Image {img['id']}: {img['size']}, filter: {img['filter']}")
    
    print(f"\n[Lattice] Total time: {elapsed:.1f} seconds")
    
    print("\n" + "=" * 60)
    print("📈 PERFORMANCE COMPARISON")
    print("=" * 60)
    sequential_time = 4 * 1 + 4 * 1.5 + 1
    print(f"""
Sequential execution (baseline): ~{sequential_time} seconds
Lattice parallel execution:      ~{elapsed:.1f} seconds

Speedup: {sequential_time / elapsed:.1f}x faster!

With more images or GPU-accelerated processing, the speedup
would be even more significant.
""")


if __name__ == "__main__":
    main()
