"""Generate disclosed benchmark replays without fabricating position or confidence evidence."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE_PATH = ROOT / "app" / "public" / "data" / "store.json"
SCANS_DIR = ROOT / "app" / "public" / "data" / "scans"

sys.path.insert(0, str(ROOT))


def run():
    # Saved predictions only: scoring labels never enter recognition/comparison.
    from server.comparison import compare_books
    SCANS_DIR.mkdir(parents=True, exist_ok=True)
    store = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "pipeline" / "benchmark_sources.json").read_text(encoding="utf-8"))
    for bay in (b for b in store["bays"] if b.get("scannable")):
        source = sources["images"][bay["photo"]]
        observations = [
            {**book, "confidence": None, "box": None,
             "box_source": "unavailable", "verification_status": "benchmark_replay"}
            for book in source["books"]
        ]
        result = {
            "bay_id": bay["id"], "bay_code": bay["code"], "bay_name": bay["name"],
            "photo_filename": bay["photo"], "photo_url": f"/photos/{bay['photo']}",
            "mode": "replay", "scanned_at": source["source_date"],
            "model": source["model"], "effort": source["effort"],
            "inference_duration_seconds": None, "tokens_used": None, "estimated_cost_usd": None,
            "selection_reason": sources["policy"],
            "source": {k: source[k] for k in ("source_path", "interface", "original_mode", "source_date")},
            "harness": {"native_resolution": False, "tile_count": 0, "calls_completed": 0,
                        "rotated_verification": False, "measured_accuracy": None},
            "disclosure": "Saved benchmark predictions. No live model call or zoom verification. Book positions and confidence were not annotated; per-photo cost and latency were not measured.",
            **compare_books(store, bay, observations),
        }
        path = SCANS_DIR / f"{bay['id']}.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Generated {bay['id']}: {source['model']}, {len(observations)} saved titles")


if __name__ == "__main__":
    run()
