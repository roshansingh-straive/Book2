"""render_outlines.py: Render AI outline bounding boxes directly onto shelf photos for QA inspection."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SCANS_DIR = ROOT / "app" / "public" / "data" / "scans"
PHOTOS_DIR = ROOT / "app" / "public" / "photos"
OUT_DIR = ROOT / "qa" / "outlines"

OUT_DIR.mkdir(parents=True, exist_ok=True)

BAYS = ["bay_f3", "bay_f1", "bay_f2", "bay_m1", "bay_a1", "bay_a2"]

for bay_id in BAYS:
    scan_file = SCANS_DIR / f"{bay_id}.json"
    if not scan_file.exists():
        continue
    with open(scan_file, encoding="utf-8") as f:
        scan = json.load(f)

    photo_path = PHOTOS_DIR / scan["photo_filename"]
    if not photo_path.exists():
        continue

    # Transpose according to EXIF so orientation matches browser
    raw_img = Image.open(photo_path)
    img = ImageOps.exif_transpose(raw_img).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    for item in scan["shelf_items"]:
        box = item["box"]
        x1 = box["left"] * w
        y1 = box["top"] * h
        x2 = (box["left"] + box["width"]) * w
        y2 = (box["top"] + box["height"]) * h

        status = item["status"]
        if status == "misplaced":
            color = (234, 88, 12)    # Amber/Orange
            width = max(3, int(w * 0.003))
        elif status == "unexpected":
            color = (147, 51, 234)   # Purple
            width = max(2, int(w * 0.002))
        else:
            color = (16, 185, 129)   # Emerald Green
            width = max(2, int(w * 0.002))

        draw.rectangle([x1, y1, x2, y2], outline=color, width=width)

    out_path = OUT_DIR / f"{bay_id}.png"
    if max(w, h) > 2000:
        ratio = 2000 / max(w, h)
        img_thumb = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
        img_thumb.save(out_path)
    else:
        img.save(out_path)

    print(f"Rendered {out_path} ({len(scan['shelf_items'])} outlines)")
