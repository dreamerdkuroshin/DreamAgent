"""Create animated GIF from DreamAgent screenshots for README."""
from PIL import Image
import os, glob

screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")

# Ordered pages to show in the demo GIF
order = [
    "dashboard.png",
    "agents.png",
    "create_agent_modal.png",
    "chat.png",
    "monitoring.png",
    "settings.png",
    "builder.png",
]

frames = []
target_size = (1280, 720)

for fname in order:
    path = os.path.join(screenshots_dir, fname)
    if os.path.exists(path):
        img = Image.open(path).convert("RGB")
        # Resize maintaining aspect ratio with letterbox
        img.thumbnail(target_size, Image.LANCZOS)
        # Pad to exact target size
        padded = Image.new("RGB", target_size, (12, 12, 20))
        offset_x = (target_size[0] - img.width) // 2
        offset_y = (target_size[1] - img.height) // 2
        padded.paste(img, (offset_x, offset_y))
        frames.append(padded)
        print(f"  + {fname} ({img.size})")
    else:
        print(f"  ! Missing: {fname}")

if frames:
    out = os.path.join(screenshots_dir, "demo.gif")
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=2500,  # 2.5 seconds per frame
        loop=0,         # loop forever
        optimize=True,
    )
    size_mb = os.path.getsize(out) / 1024 / 1024
    print(f"\nGIF saved: {out} ({size_mb:.1f} MB, {len(frames)} frames)")
else:
    print("No frames found!")
